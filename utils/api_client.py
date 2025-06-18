import os
import requests
import logging
import json
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlencode

logger = logging.getLogger("KindergartenApp")


class ApiClientError(Exception):
    def __init__(self, message="API Client Error", status_code=None, details=None):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)

    def __str__(self):
        return f"{self.__class__.__name__}: {self.message}"


class ApiConnectionError(ApiClientError):
    def __init__(self, url: str, original_exception: Exception):
        super().__init__(
            message=f"Не удалось подключиться к серверу по адресу {url}",
            details=str(original_exception),
        )


class ApiTimeoutError(ApiClientError):
    def __init__(self, url: str):
        super().__init__(message=f"Превышено время ожидания ответа от {url}")


class ApiHttpError(ApiClientError):
    def __init__(self, status_code: int, url: str, response_text: Optional[str] = None):
        message = f"Ошибка HTTP {status_code} от {url}"
        details_dict = None
        detail_message = ""
        if response_text:
            try:
                details_dict = json.loads(response_text)
                if isinstance(details_dict, dict) and "detail" in details_dict:
                    detail_content = details_dict["detail"]
                    if (
                        isinstance(detail_content, list)
                        and len(detail_content) > 0
                        and isinstance(detail_content[0], dict)
                    ):
                        first_error = detail_content[0]
                        error_msg = f"{first_error.get('msg', 'Ошибка валидации')} (Поле: {' -> '.join(map(str, first_error.get('loc', ['?'])))})"
                        detail_message = error_msg
                    elif isinstance(detail_content, str):
                        detail_message = detail_content
                    else:
                        detail_message = str(detail_content)
                elif details_dict is not None and not detail_message:
                    detail_message = f"Ответ сервера: {str(details_dict)[:150]}"
            except json.JSONDecodeError:
                detail_message = f"Текст ответа: {response_text[:200]}"
        if detail_message:
            message += f": {detail_message}"
        super().__init__(
            message=message,
            status_code=status_code,
            details=details_dict if details_dict is not None else response_text,
        )


# --- Класс API Клиента ---
class ApiClient:
    def __init__(self, base_url: str, timeout: int = 15):
        self.base_url = base_url.replace("/api", "").strip("/")
        self.token: Optional[str] = None
        self.current_user: Optional[Dict] = None
        self.timeout = timeout
        self.session = requests.Session()
        self.session.timeout = timeout
        logger.info(
            f"API Client initialized for base URL: {self.base_url} with timeout {timeout}s"
        )

    def set_token(self, token: Optional[str]):
        self.token = token
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            logger.debug("API token set.")
        else:
            if "Authorization" in self.session.headers:
                del self.session.headers["Authorization"]
            self.current_user = None
            logger.debug("API token removed.")

    def _clear_session_state(self):
        """Сбрасывает токен и информацию о пользователе."""
        self.set_token(None)

    def login(self, username: str, password: str) -> bool:
        """
        Выполняет вход, получает токен и информацию о пользователе.
        Возвращает True в случае успеха, иначе False.
        В случае HTTP ошибок (кроме 401) или сетевых ошибок, выбрасывает исключения.
        """
        login_url = f"{self.base_url}/api/auth/token"
        data = {"username": username, "password": password}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        logger.info(f"Attempting login for user '{username}' to {login_url}")

        self._clear_session_state()

        try:
            response = self.session.post(login_url, data=data, headers=headers)

            if response.status_code == 200:
                try:
                    token_data = response.json()
                    if (
                        "access_token" in token_data
                        and token_data.get("token_type", "").lower() == "bearer"
                    ):
                        self.set_token(token_data["access_token"])

                        # После установки токена, получаем информацию о пользователе
                        if self.fetch_current_user_info():
                            logger.info(
                                f"Login and user info fetch successful for user '{self.current_user.get('username') if self.current_user else username}'."
                            )
                            return True
                        else:
                            logger.error(
                                f"Login for '{username}' successful (token received), but failed to fetch user info."
                            )
                            self._clear_session_state()
                            return False
                    else:
                        logger.error(
                            f"Login failed for '{username}': Invalid token data received: {token_data}"
                        )
                        return False
                except json.JSONDecodeError:
                    logger.error(
                        f"Login failed for '{username}': Could not decode JSON from {login_url}. Status: {response.status_code}"
                    )
                    return False
            elif response.status_code == 401:
                logger.warning(
                    f"Login failed for user '{username}': Invalid credentials (401)."
                )
                return False
            else:
                raise ApiHttpError(response.status_code, login_url, response.text)

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Login failed: Connection Error to {login_url}. Error: {e}")
            raise ApiConnectionError(login_url, e) from e
        except requests.exceptions.Timeout as e:
            logger.error(f"Login failed: Timeout to {login_url}.")
            raise ApiTimeoutError(login_url) from e
        except requests.exceptions.RequestException as e:
            logger.exception(
                f"Unexpected requests error during login for '{username}': {e}"
            )
            raise ApiClientError(f"Unexpected API error during login: {e}") from e

    def fetch_current_user_info(self) -> bool:
        """
        Запрашивает и сохраняет информацию о текущем аутентифицированном пользователе.
        Возвращает True в случае успеха, иначе False.
        """
        if not self.token:
            logger.warning("Cannot fetch user info: no token available.")
            return False

        endpoint = "/auth/me"
        url = f"{self.base_url}/api{endpoint if endpoint.startswith('/') else '/' + endpoint}"
        logger.debug(f"Fetching current user info from {url}")
        try:

            response = self._request("GET", endpoint)
            self.current_user = self._parse_json_response(response, f"GET {endpoint}")
            if self.current_user and "username" in self.current_user:
                logger.info(
                    f"Successfully fetched user info for: {self.current_user.get('username')}"
                )
                return True
            else:
                logger.error(
                    f"Fetched user info is invalid or incomplete: {self.current_user}"
                )
                self.current_user = None
                return False
        except ApiHttpError as e:
            logger.error(f"HTTP error fetching user info: {e.message}")
            self.current_user = None
            return False
        except ApiClientError as e:
            logger.error(f"API client error fetching user info: {e.message}")
            self.current_user = None
            return False
        except Exception as e:
            logger.exception(f"Unexpected error fetching user info: {e}")
            self.current_user = None
            return False

    def get_current_user_details(self) -> Optional[Dict]:
        """Возвращает сохраненную информацию о текущем пользователе."""
        return self.current_user

    def logout(self):
        self.set_token(None)
        logger.info("User logged out, session state cleared.")

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:

        clean_endpoint = (
            endpoint.removeprefix("/api/")
            .removeprefix("/api")
            .removeprefix("/")
            .strip("/")
        )
        url = f"{self.base_url}/api/{clean_endpoint}"
        log_url = url
        if "params" in kwargs and kwargs.get("params"):
            try:
                log_url += f"?{urlencode(kwargs['params'])}"
            except Exception:
                pass

        is_login_request = endpoint.strip("/") == "auth/token"

        # Проверяем токен для всех запросов, кроме запроса на логин
        if not self.token and not is_login_request:
            logger.error(
                f"API error: No token for {log_url}. Current endpoint: '{endpoint}' is_login_request: {is_login_request}"
            )
            raise ApiClientError("Authentication token not available.", status_code=401)

        logger.debug(f"Sending {method} request to {log_url}")
        try:
            response = self.session.request(method, url, **kwargs)
            if response.status_code >= 400:
                # Для 401 (Unauthorized) из-за истекшего/неверного токена, сбрасываем состояние сессии
                if response.status_code == 401 and not is_login_request:
                    logger.warning(
                        f"Received 401 Unauthorized for {url}. Clearing session state."
                    )
                    self._clear_session_state()
                raise ApiHttpError(response.status_code, url, response.text)
            return response
        except requests.exceptions.ConnectionError as e:
            logger.error(f"API ConnectionError to {url}: {e}")
            raise ApiConnectionError(url, e) from e
        except requests.exceptions.Timeout as e:
            logger.error(f"API Timeout to {url}.")
            raise ApiTimeoutError(url) from e
        except requests.exceptions.RequestException as e:
            logger.exception(f"API RequestException for {method} {url}: {e}")
            raise ApiClientError(f"Network/Request error: {e}") from e

    def _parse_json_response(
        self, response: requests.Response, endpoint_info: str
    ) -> Any:
        try:
            return response.json()
        except json.JSONDecodeError:
            logger.error(
                f"JSONDecodeError from {endpoint_info}. Status: {response.status_code}, Text: {response.text[:200]}"
            )
            raise ApiClientError(
                f"Invalid JSON response from server for {endpoint_info}."
            )

    # --- Методы для API Групп ---
    def get_groups(self, skip: int = 0, limit: int = 1000) -> List[Dict]:
        endpoint = "/groups/"
        params = {"skip": skip, "limit": limit}
        response = self._request("GET", endpoint, params=params)
        return self._parse_json_response(response, f"GET {endpoint}")

    def get_group(self, group_id: int) -> Dict:
        endpoint = f"/groups/{group_id}"
        response = self._request("GET", endpoint)
        return self._parse_json_response(response, f"GET {endpoint}")

    def create_group(self, group_data: Dict) -> Dict:
        endpoint = "/groups/"
        response = self._request("POST", endpoint, json=group_data)
        return self._parse_json_response(response, f"POST {endpoint}")

    def update_group(self, group_id: int, group_data: Dict) -> Dict:
        endpoint = f"/groups/{group_id}"
        response = self._request("PUT", endpoint, json=group_data)
        return self._parse_json_response(response, f"PUT {endpoint}")

    def delete_group(self, group_id: int) -> bool:
        endpoint = f"/groups/{group_id}"
        try:
            response = self._request("DELETE", endpoint)
            return response.status_code == 204
        except ApiHttpError as e:
            logger.error(f"Delete group {group_id} failed: {e.message}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error deleting group {group_id}: {e}")
            return False

    # --- Методы для API Меню ---
    def get_menus(self, start_date: str, end_date: str) -> List[Dict]:
        endpoint = "/menus/"
        params = {"start_date": start_date, "end_date": end_date}
        response = self._request("GET", endpoint, params=params)
        return self._parse_json_response(response, f"GET {endpoint}")

    def upsert_menu(self, menu_data: Dict) -> Optional[Dict]:
        endpoint = "/menus/"
        response = self._request("POST", endpoint, json=menu_data)
        return (
            None
            if response.status_code == 204
            else self._parse_json_response(response, f"POST {endpoint}")
        )

    def delete_menu(self, menu_id: int) -> bool:
        endpoint = f"/menus/{menu_id}"
        try:
            response = self._request("DELETE", endpoint)
            return response.status_code == 204
        except ApiHttpError as e:
            logger.error(f"Delete menu {menu_id} failed: {e.message}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error deleting menu {menu_id}: {e}")
            return False

    # --- Методы для API Пользователей (Users) ---
    def get_users(
        self, role: Optional[str] = None, skip: int = 0, limit: int = 200
    ) -> List[Dict]:
        endpoint = "/users/"
        params = {"skip": skip, "limit": limit}
        if role:
            params["role"] = role
        response = self._request("GET", endpoint, params=params)
        return self._parse_json_response(response, f"GET {endpoint}")

    def get_teachers(self) -> List[Dict]:
        try:
            return self.get_users(role="teacher", limit=200)
        except ApiHttpError as e:
            if e.status_code == 403:
                logger.warning("Get teachers failed (403 Forbidden from API).")
            else:

                logger.error(f"Get teachers failed with HTTP error: {e.message}")
                raise e
            return []
        except Exception as e:
            logger.exception(f"Unexpected error in get_teachers: {e}")
            raise ApiClientError(f"Could not load teachers: {e}") from e

    def get_user(self, user_id: int) -> Dict:
        endpoint = f"/users/{user_id}"
        response = self._request("GET", endpoint)
        return self._parse_json_response(response, f"GET {endpoint}")

    def create_user(self, user_data: Dict) -> Dict:
        endpoint = "/users/"
        response = self._request("POST", endpoint, json=user_data)
        return self._parse_json_response(response, f"POST {endpoint}")

    def update_user(self, user_id: int, user_data: Dict) -> Dict:
        endpoint = f"/users/{user_id}"
        response = self._request("PUT", endpoint, json=user_data)
        return self._parse_json_response(response, f"PUT {endpoint}")

    def delete_user(self, user_id: int) -> bool:
        endpoint = f"/users/{user_id}"
        try:
            response = self._request("DELETE", endpoint)
            return response.status_code == 204
        except ApiHttpError as e:
            logger.error(f"Delete user {user_id} failed: {e.message}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error deleting user {user_id}: {e}")
            return False

    # --- Методы для API Детей (Children) ---
    def get_children(
        self,
        group_id: Optional[int] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 200,
    ) -> List[Dict]:
        endpoint = "/children/"
        params: Dict[str, Any] = {
            "skip": skip,
            "limit": limit,
        }
        if group_id is not None:
            params["group_id"] = group_id
        if search:
            params["search"] = search
        response = self._request("GET", endpoint, params=params)
        return self._parse_json_response(response, f"GET {endpoint}")

    def get_child(self, child_id: int) -> Dict:
        endpoint = f"/children/{child_id}"
        response = self._request("GET", endpoint)
        return self._parse_json_response(response, f"GET {endpoint}")

    def create_child(self, child_data: Dict) -> Dict:
        endpoint = "/children/"
        response = self._request("POST", endpoint, json=child_data)
        return self._parse_json_response(response, f"POST {endpoint}")

    def update_child(self, child_id: int, child_data: Dict) -> Dict:
        endpoint = f"/children/{child_id}"
        response = self._request("PUT", endpoint, json=child_data)
        return self._parse_json_response(response, f"PUT {endpoint}")

    def delete_child(self, child_id: int) -> bool:
        endpoint = f"/children/{child_id}"
        try:
            response = self._request("DELETE", endpoint)
            return response.status_code == 204
        except ApiHttpError as e:
            logger.error(f"Delete child {child_id} failed: {e.message}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error deleting child {child_id}: {e}")
            return False

    # --- Методы для управления связями Ребенок-Родитель ---
    def get_child_parents(self, child_id: int) -> List[Dict]:
        endpoint = f"/children/{child_id}/parents"
        response = self._request("GET", endpoint)
        return self._parse_json_response(response, f"GET {endpoint}")

    def add_parent_to_child(
        self, child_id: int, parent_id: int, relation_type: str
    ) -> Dict:
        endpoint = f"/children/{child_id}/parents"
        payload = {"parent_id": parent_id, "relation_type": relation_type}
        response = self._request("POST", endpoint, json=payload)
        return self._parse_json_response(response, f"POST {endpoint}")

    def remove_parent_from_child(self, child_id: int, parent_id: int) -> bool:
        endpoint = f"/children/{child_id}/parents/{parent_id}"
        try:
            response = self._request("DELETE", endpoint)
            return response.status_code == 204
        except ApiHttpError as e:
            logger.error(
                f"Remove parent {parent_id} from child {child_id} failed: {e.message}"
            )
            return False
        except Exception as e:
            logger.exception(
                f"Unexpected error removing parent {parent_id} from child {child_id}: {e}"
            )
            return False

    # --- Методы для API Посещаемости (Attendance) ---
    def get_attendance(
        self,
        attendance_date: str,
        group_id: Optional[int] = None,
        child_id: Optional[int] = None,
    ) -> List[Dict]:
        endpoint = "/attendance/"
        params: Dict[str, Any] = {"attendance_date": attendance_date}
        if group_id is not None:
            params["group_id"] = group_id
        if child_id is not None:
            params["child_id"] = child_id
        response = self._request("GET", endpoint, params=params)
        return self._parse_json_response(response, f"GET {endpoint}")

    def create_attendance_record(self, attendance_data: Dict) -> Dict:
        endpoint = "/attendance/"
        response = self._request("POST", endpoint, json=attendance_data)
        return self._parse_json_response(response, f"POST {endpoint}")

    def update_attendance_record(
        self, attendance_id: int, attendance_data: Dict
    ) -> Dict:
        endpoint = f"/attendance/{attendance_id}"
        response = self._request("PUT", endpoint, json=attendance_data)
        return self._parse_json_response(response, f"PUT {endpoint}")

    def delete_attendance_record(self, attendance_id: int) -> bool:
        endpoint = f"/attendance/{attendance_id}"
        try:
            response = self._request("DELETE", endpoint)
            return response.status_code == 204
        except ApiHttpError as e:
            logger.error(f"Delete attendance {attendance_id} failed: {e.message}")
            return False
        except Exception as e:
            logger.exception(
                f"Unexpected error deleting attendance {attendance_id}: {e}"
            )
            return False

    def bulk_create_attendance(self, bulk_data: Dict) -> List[Dict]:
        endpoint = "/attendance/bulk"
        response = self._request("POST", endpoint, json=bulk_data)
        return self._parse_json_response(response, f"POST {endpoint}")

    # --- Методы для API Праздников/Выходных (Holidays) ---
    def get_holidays(self, start_date: str, end_date: str) -> List[Dict]:
        endpoint = "/holidays/"
        params = {"start_date": start_date, "end_date": end_date}
        response = self._request("GET", endpoint, params=params)
        return self._parse_json_response(response, f"GET {endpoint}")

    def add_holiday(self, holiday_data: Dict) -> Dict:
        endpoint = "/holidays/"
        response = self._request("POST", endpoint, json=holiday_data)
        return self._parse_json_response(response, f"POST {endpoint}")

    def delete_holiday(self, holiday_date: str) -> bool:  # Принимает дату YYYY-MM-DD
        endpoint = "/holidays/by_date"

        payload = {"date": holiday_date}
        try:
            response = self._request("DELETE", endpoint, json=payload)
            return response.status_code == 204
        except ApiHttpError as e:
            logger.error(f"Delete holiday on {holiday_date} failed: {e.message}")
            return False
        except Exception as e:
            logger.exception(
                f"Unexpected error deleting holiday on {holiday_date}: {e}"
            )
            return False

    # --- Методы для API Отчетов ---
    def download_attendance_report(
        self,
        group_id: int,
        year: int,
        month: int,
        default_rate: Optional[float],
        staff_rates: Dict[int, float],
    ) -> bytes:
        endpoint = "/reports/attendance"
        payload = {
            "group_id": group_id,
            "year": year,
            "month": month,
            "default_rate": default_rate,
            "staff_rates": staff_rates if staff_rates else {},
        }
        logger.info(
            f"Requesting attendance report: group={group_id}, year={year}, month={month}"
        )
        logger.debug(f"Report request payload: {payload}")

        clean_endpoint = (
            endpoint.removeprefix("/api/")
            .removeprefix("/api")
            .removeprefix("/")
            .strip("/")
        )
        url = f"{self.base_url}/api/{clean_endpoint}"

        try:

            response = self.session.post(url, json=payload, stream=True)

            if response.status_code == 200:
                content_type = response.headers.get("content-type", "").lower()
                if (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    in content_type
                ):
                    logger.info(
                        "Attendance report received successfully (binary data)."
                    )
                    return response.content
                else:
                    logger.error(
                        f"Unexpected content type for report: {content_type}. Expected Excel."
                    )
                    error_text = response.text
                    raise ApiClientError(
                        f"Server returned unexpected content type for report: {content_type}. Response: {error_text[:200]}"
                    )
            else:

                raise ApiHttpError(response.status_code, url, response.text)
        except requests.exceptions.ConnectionError as e:
            logger.error(
                f"Report request failed: Connection Error to {url}. Error: {e}"
            )
            raise ApiConnectionError(url, e) from e
        except requests.exceptions.Timeout as e:
            logger.error(f"Report request failed: Timeout to {url}.")
            raise ApiTimeoutError(url) from e
        except requests.exceptions.RequestException as e:
            logger.exception(f"An unexpected requests error during report request: {e}")
            raise ApiClientError(f"Network/Request error for report: {e}") from e

    def calculate_and_save_monthly_charges(self, payload: Dict) -> List[Dict]:
        """Рассчитывает и сохраняет ежемесячные начисления."""
        endpoint = "/api/payments/charge-monthly"
        response_obj = self._request("POST", endpoint, json=payload)
        parsed_data = self._parse_json_response(response_obj, f"POST {endpoint}")
        return parsed_data if isinstance(parsed_data, list) else []

    def get_monthly_charges(
        self,
        child_id: Optional[int] = None,
        group_id: Optional[int] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> List[Dict]:
        """
        Получает историю ежемесячных начислений.
        - Если указан child_id, получает историю для ребенка.
        - Если указан group_id, year и month, получает историю для группы за этот период.
        - Если не указан ни child_id, ни group_id.
        """
        params = {}
        if year:
            params["year"] = year
        if month:
            params["month"] = month

        endpoint_str = ""

        if child_id is not None:
            endpoint = f"children/{child_id}/monthly-charges"

            if "month" in params and year is None:
                del params["month"]
            endpoint_str = endpoint
        elif group_id is not None:
            if not (year and month):
                logger.warning(
                    "get_monthly_charges: For group_id, year and month are currently required by this client method."
                )
                #
                return []
            endpoint = f"payments/groups/{group_id}/monthly-charges"
            endpoint_str = endpoint
        else:
            logger.warning(
                "get_monthly_charges: Either child_id or (group_id with year and month) must be provided."
            )
            return []

        logger.debug(
            f"ApiClient: Calling get_monthly_charges. Endpoint: {endpoint}, Params: {params}"
        )
        response_obj = self._request("GET", endpoint, params=params)
        parsed_data = self._parse_json_response(response_obj, f"GET {endpoint_str}")

        if isinstance(parsed_data, list):
            return parsed_data
        elif parsed_data is None:
            logger.info(
                f"Received None or empty response after parsing for {endpoint_str}. Returning empty list."
            )
            return []
        else:
            logger.error(
                f"Unexpected data type from _parse_json_response for {endpoint_str}: {type(parsed_data)}. Expected list."
            )

            raise ApiClientError(
                f"API вернул неожиданный формат данных для {endpoint_str}."
            )

    # --- Методы для API Постов ---
    def get_posts(
        self,
        skip: int = 0,
        limit: int = 20,
        pinned_only: Optional[bool] = None,
    ) -> List[Dict]:
        """Получает список постов с сервера."""
        endpoint = "posts/"
        params: Dict[str, Any] = {"skip": skip, "limit": limit}
        if pinned_only is not None:
            params["pinned_only"] = pinned_only

        logger.debug(f"ApiClient: Requesting posts with params: {params}")
        response = self._request("GET", endpoint, params=params)
        return self._parse_json_response(response, f"GET {endpoint}")

    def get_post(self, post_id: int) -> Dict:
        """Получает один пост по ID."""
        endpoint = f"posts/{post_id}"
        response = self._request("GET", endpoint)
        return self._parse_json_response(response, f"GET {endpoint}")

    def create_post_text(
        self, title: Optional[str], text_content: str, is_pinned: bool = False
    ) -> Dict:
        """Создает пост только с текстовыми данными."""
        endpoint = "posts/"
        payload = {
            "title": title,
            "text_content": text_content,
            "is_pinned": is_pinned,
        }

        payload_cleaned = {
            k: v
            for k, v in payload.items()
            if v is not None or k == "text_content" or k == "is_pinned"
        }

        form_data: Dict[str, Any] = {}
        if title is not None:
            form_data["title"] = title
        form_data["text_content"] = text_content
        form_data["is_pinned"] = is_pinned

        logger.debug(f"ApiClient: Creating text post with form_data: {form_data}")

        raise NotImplementedError(
            "create_post_text needs to be adapted for Form() params or server endpoint needs change for JSON body."
        )

    def create_post_with_image(
        self,
        title: Optional[str],
        text_content: str,
        is_pinned: bool,
        image_path: Optional[str],
    ) -> Dict:
        """Создает пост с текстом и опциональным изображением."""
        endpoint = "posts/"

        data_payload: Dict[str, Any] = {}
        if title is not None:
            data_payload["title"] = title
        data_payload["text_content"] = text_content
        data_payload["is_pinned"] = is_pinned

        files_payload = None
        request_kwargs = {"data": data_payload}

        if image_path:
            try:

                import mimetypes

                content_type, _ = mimetypes.guess_type(image_path)
                if content_type is None:
                    content_type = "application/octet-stream"

                files_payload = {
                    "image_file": (
                        os.path.basename(image_path),
                        open(image_path, "rb"),
                        content_type,
                    )
                }
                request_kwargs["files"] = files_payload
                logger.debug(
                    f"ApiClient: Creating post. Data: {data_payload}, File: {image_path}"
                )
            except FileNotFoundError:
                logger.error(f"Image file not found at {image_path} for creating post.")
                raise ApiClientError(f"Файл изображения не найден: {image_path}")
            except Exception as e:
                logger.error(f"Error preparing image for upload: {e}")
                raise ApiClientError(f"Ошибка подготовки изображения: {e}")
        else:
            logger.debug(
                f"ApiClient: Creating post without image. Data: {data_payload}"
            )

        response = self._request("POST", endpoint, **request_kwargs)

        return self._parse_json_response(
            response, f"POST {endpoint} (with/without image)"
        )

    def update_post_text(
        self,
        post_id: int,
        title: Optional[str],
        text_content: Optional[str],
        is_pinned: Optional[bool],
    ) -> Dict:
        """Обновляет текстовые данные поста."""
        endpoint = f"posts/{post_id}"
        payload = {}
        if title is not None:
            payload["title"] = title
        if text_content is not None:
            payload["text_content"] = text_content
        if is_pinned is not None:
            payload["is_pinned"] = is_pinned

        if not payload:
            return self.get_post(post_id)

        response = self._request("PUT", endpoint, json=payload)
        return self._parse_json_response(response, f"PUT {endpoint} text data")

    def upload_post_image(self, post_id: int, image_path: str) -> Dict:
        """Загружает/заменяет изображение для поста."""
        endpoint = f"posts/{post_id}/image"
        try:
            with open(image_path, "rb") as f_img:
                files = {
                    "image_file": (os.path.basename(image_path), f_img, "image/jpeg")
                }
                response = self._request("POST", endpoint, files=files)
        except FileNotFoundError:
            logger.error(f"Image file not found at {image_path} for post {post_id}.")
            raise ApiClientError(f"Файл изображения не найден: {image_path}")
        except Exception as e:
            logger.error(f"Error preparing image for upload for post {post_id}: {e}")
            raise ApiClientError(f"Ошибка подготовки изображения: {e}")

        return self._parse_json_response(response, f"POST {endpoint} image")

    def delete_post_image(self, post_id: int) -> Dict:
        """Удаляет изображение у поста."""
        endpoint = f"posts/{post_id}/image"
        response = self._request("DELETE", endpoint)
        return self._parse_json_response(response, f"DELETE {endpoint} image")

    def delete_post(self, post_id: int) -> bool:
        """Удаляет пост."""
        endpoint = f"posts/{post_id}"
        try:
            response = self._request("DELETE", endpoint)
            return response.status_code == 204
        except ApiHttpError as e:
            logger.error(f"Delete post {post_id} failed: {e.message}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error deleting post {post_id}: {e}")
            return False

    def get_image_bytes(self, relative_media_path: str) -> Optional[bytes]:
        """
        Загружает медиафайл (изображение) как байты с сервера.
        relative_media_path: Относительный путь к файлу внутри папки uploads
        (например, "post_media/image.jpg" или "avatars/user.png").
        """
        if not relative_media_path:
            logger.warning("get_image_bytes_v2 called with empty relative_media_path.")
            return None

        clean_relative_path = relative_media_path.lstrip("/")
        url = f"{self.base_url}/uploads/{clean_relative_path}"

        logger.debug(f"ApiClient: Fetching image bytes from URL: {url}")
        try:

            response = self.session.get(url, timeout=self.timeout, stream=True)
            response.raise_for_status()

            image_bytes = response.content
            logger.debug(
                f"ApiClient: Successfully fetched {len(image_bytes)} bytes for image {url}"
            )
            return image_bytes

        except requests.exceptions.HTTPError as e:
            logger.error(
                f"HTTP error fetching image from {url}: {e.response.status_code} - {e.response.text[:100]}"
            )
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error fetching image from {url}: {e}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching image from {url}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Generic error fetching image from {url}: {e}")
        return None

    # --- Методы для API Уведомлений/Событий ---
    def create_notification(self, notification_data: Dict) -> Dict:
        """Создает новое уведомление или событие."""
        endpoint = "notifications/"
        logger.debug(
            f"ApiClient: Creating notification/event with data: {notification_data}"
        )
        response = self._request("POST", endpoint, json=notification_data)
        return self._parse_json_response(response, f"POST {endpoint}")

    def get_notifications(
        self,
        skip: int = 0,
        limit: int = 100,
        audience: Optional[str] = None,
        is_event: Optional[bool] = None,
    ) -> List[Dict]:
        """Получает список уведомлений/событий."""
        endpoint = "notifications/"
        params: Dict[str, Any] = {"skip": skip, "limit": limit}
        if audience is not None:
            params["audience"] = audience
        if is_event is not None:
            params["is_event"] = is_event
        logger.debug(f"ApiClient: Requesting notifications with params: {params}")
        response = self._request("GET", endpoint, params=params)
        return self._parse_json_response(response, f"GET {endpoint}")

    def get_notification(self, notification_id: int) -> Dict:
        """Получает одно уведомление/событие по ID."""
        endpoint = f"notifications/{notification_id}"
        response = self._request("GET", endpoint)
        return self._parse_json_response(response, f"GET {endpoint}")

    def update_notification(
        self, notification_id: int, notification_data: Dict
    ) -> Dict:
        """Обновляет существующее уведомление или событие."""
        endpoint = f"notifications/{notification_id}"
        logger.debug(
            f"ApiClient: Updating notification/event ID {notification_id} with data: {notification_data}"
        )
        response = self._request("PUT", endpoint, json=notification_data)
        return self._parse_json_response(response, f"PUT {endpoint}")

    def delete_notification(self, notification_id: int) -> bool:
        """Удаляет уведомление или событие."""
        endpoint = f"notifications/{notification_id}"
        logger.debug(f"ApiClient: Deleting notification/event ID {notification_id}")
        try:
            response = self._request("DELETE", endpoint)
            return response.status_code == 204
        except ApiHttpError as e:
            logger.error(f"Delete notification {notification_id} failed: {e.message}")
            raise e
        except Exception as e:
            logger.exception(
                f"Unexpected error deleting notification {notification_id}: {e}"
            )
            raise ApiClientError(f"Не удалось удалить уведомление: {e}") from e
