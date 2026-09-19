class IdentifierConflictError(Exception):
    def __init__(self, identifier_name: str, identifier_value: str) -> None:
        self.identifier_name = identifier_name
        self.identifier_value = identifier_value
        super().__init__(f"{identifier_name} already exists with different content")
