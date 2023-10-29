class KeyCache:
    """A store for OpenPGP keys.

    Key case is sanitised while loading from GnuPG if so
    configured.  See mail_case_insensitive parameter in section
    [default].
    """

    def __init__(self, keys: dict = None):
        """Initialise an empty cache.

        With keyring_dir given, set location of the directory from which keys should be loaded.
        """
        self._keys = keys

    def __getitem__(self, fingerpring):
        """Look up email assigned to the given fingerprint."""
        return self._keys[fingerpring]

    def __setitem__(self, fingerprint, email):
        """Assign an email to a fingerpring, overwriting it if it was already present."""
        self._keys[fingerprint] = email

    def __contains__(self, fingerprint):
        """Check if the given fingerprint is assigned to an email."""
        # This method has to be present for KeyCache to be a dict substitute.
        # See mailgate, function _identify_gpg_recipients.
        return fingerprint in self._keys

    def has_email(self, email):
        """Check if cache contains a key assigned to the given email."""
        return email in self._keys.values()

    def __repr__(self):
        """Return text representation of this object."""
        details = ' '.join(self._keys.keys())
        return '<KeyCache %s>' % (details)


class KeyRing:
    """Contract to be implemented by a key-store (a.k.a. keyring)."""

    def load(self):
        """Load keyring, replacing any previous contents of the cache."""
        raise NotImplementedError('KeyRing.load not implemented')

    def freeze_identities(self) -> KeyCache:
        """Return a static, async-safe copy of the identity map."""
        raise NotImplementedError('KeyRing.load not implemented')

    def register(self, email: str, key_id: str):
        """Add a new (email,key) pair to the keystore."""
        raise NotImplementedError('KeyRing.register not implemented')

    def post_init_hook(self):
        """Lets the keyring perform additional operations following its initialisation."""
        pass

    def shutdown(self):
        """Lets the keyring perform operations prior to shutting down."""
        pass
