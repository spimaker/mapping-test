from ._anvil_designer import QRCodeTemplate
from anvil import alert, open_form
import anvil.server


class QRCode(QRCodeTemplate):
    def __init__(self, **properties):
        # Set Form properties and Data Bindings.
        self.init_components(**properties)
        self._load_existing_qr_code()

    def _set_make_button_visible(self, visible: bool):
        if hasattr(self, "Make_qr_code") and self.Make_qr_code is not None:
            self.Make_qr_code.visible = visible
        elif hasattr(self, "make_qr_code") and self.make_qr_code is not None:
            self.make_qr_code.visible = visible

    def _set_make_button_enabled(self, enabled: bool):
        if hasattr(self, "Make_qr_code") and self.Make_qr_code is not None:
            self.Make_qr_code.enabled = enabled
        elif hasattr(self, "make_qr_code") and self.make_qr_code is not None:
            self.make_qr_code.enabled = enabled

    def _load_existing_qr_code(self):
        """Load saved QR code from User_profile if present; toggle Make_qr_code visibility."""
        try:
            user_name = anvil.server.call("get_authenticated_user_name")
            if not user_name:
                self._set_make_button_visible(True)
                return

            saved_qr = anvil.server.call("get_user_qr_media", username=user_name)
            if saved_qr is not None:
                self.qr_code_image.source = saved_qr
                self._set_make_button_visible(False)
            else:
                self._set_make_button_visible(True)
        except Exception as e:
            print(f"Error loading saved QR code: {e}")
            self._set_make_button_visible(True)

    def make_qr_code_click(self, **event_args):
        """Prompt to log in if needed; otherwise generate, save, and display the QR code."""
        self._set_make_button_enabled(False)
        try:
            user_name = anvil.server.call("get_authenticated_user_name")
            if not user_name:
                go_to_login = alert(
                    "You must be logged in to create a QR Code.",
                    title="Login Required",
                    buttons=[("Log In / Register", True), ("Cancel", False)],
                )
                if go_to_login:
                    open_form("Layouts.NavLayout.Login_register")
                return

            qr_media = anvil.server.call(
                "generate_user_qr_media",
                username=user_name,
                top_text="Join me on\nthe Map",
                bottom_text="Naturist Map",
            )
            self.qr_code_image.source = qr_media
            if qr_media is not None:
                self._set_make_button_visible(False)
        finally:
            self._set_make_button_enabled(True)