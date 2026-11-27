from ._anvil_designer import QRCodeTemplate
from anvil import alert, open_form
import anvil.server
import anvil.users


class QRCode(QRCodeTemplate):
    def __init__(self, **properties):
        # Set Form properties and Data Bindings.
        self.init_components(**properties)

    def make_qr_code_click(self, **event_args):
        """Prompt to log in if needed; otherwise generate and display the user's QR code."""
        user = anvil.users.get_user()
        print("QRCode current user:", user)

        if not user:
            go_to_login = alert(
                "You must be logged in to create a QR Code.",
                title="Login Required",
                buttons=[("Log In / Register", True), ("Cancel", False)],
            )
            if go_to_login:
                open_form("Layouts.NavLayout.Login_register")
            return

        self.make_qr_code.enabled = False
        try:
            self.qr_code_image.source = anvil.server.call("generate_user_qr_media")
        finally:
            self.make_qr_code.enabled = True