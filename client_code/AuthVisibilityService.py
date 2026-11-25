import anvil.server
import anvil.users


class _AuthVisibilityService:
  def __init__(self):
    self._is_logged_in = None
    self._user = None
    # Registry of feature_key -> rule ('logged_in' | 'logged_out' | callable(is_logged_in, user) -> bool)
    self._feature_rules = {
        "map_my_location": "logged_in",
        "login_register_link": "logged_out",
        "logout_link": "logged_in",
        # Add future features here, e.g.:
        # 'profile': 'logged_in',
        # 'have_done': 'logged_in',
    }
    # List of (component, feature_key, attr)
    self._bindings = []

  def set_logged_in(self, is_logged_in, user=None):
    """Explicitly update auth state and re-apply all bound components."""
    self._is_logged_in = bool(is_logged_in)
    self._user = user
    self.apply_all_bindings()
    return self._is_logged_in

  def refresh_auth_state(self):
    """Checks server session first, falling back to anvil.users.get_user(), then updates bindings."""
    logged_in = False
    user_info = None

    try:
      session_user = anvil.server.call("get_authenticated_user")
      if session_user:
        logged_in = True
        user_info = session_user
    except Exception:
      pass

    if not logged_in:
      try:
        u = anvil.users.get_user()
        if u is not None:
          logged_in = True
          user_info = u
      except Exception:
        pass

    return self.set_logged_in(logged_in, user_info)

  @property
  def is_logged_in(self):
    if self._is_logged_in is None:
      self.refresh_auth_state()
    return bool(self._is_logged_in)

  @property
  def current_user(self):
    if self._is_logged_in is None:
      self.refresh_auth_state()
    return self._user

  def register_feature(self, feature_key, rule="logged_in"):
    """Register or override a feature visibility rule dynamically."""
    self._feature_rules[feature_key] = rule
    self.apply_all_bindings()

  def is_feature_enabled(self, feature_key):
    """Evaluate whether a feature should be visible/enabled for the current auth state."""
    logged_in = self.is_logged_in
    rule = self._feature_rules.get(feature_key, "logged_in")

    if callable(rule):
      return bool(rule(logged_in, self._user))
    if rule == "logged_in":
      return logged_in
    if rule == "logged_out":
      return not logged_in
    return bool(rule)

  def bind(self, component, feature_key, attr="visible"):
    """Bind a UI component property (default: 'visible') to a feature key and apply immediately."""
    if component is None:
      return
    self._bindings = [
        b for b in self._bindings if not (b[0] is component and b[2] == attr)
    ]
    self._bindings.append((component, feature_key, attr))
    setattr(component, attr, self.is_feature_enabled(feature_key))

  def apply_all_bindings(self):
    """Re-evaluate visibility for every registered UI component."""
    active_bindings = []
    for component, feature_key, attr in self._bindings:
      try:
        setattr(component, attr, self.is_feature_enabled(feature_key))
        active_bindings.append((component, feature_key, attr))
      except Exception:
        pass
    self._bindings = active_bindings


auth_visibility = _AuthVisibilityService()