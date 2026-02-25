"""
Abstract base class for plate reader data parsers.

PRD Reference: Section 1.2 - Parser extensibility architecture

This module provides the base interface for all plate reader file parsers,
enabling support for multiple instrument formats while maintaining a
consistent API for the application.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Union
from pathlib import Path


class BaseParser(ABC):
    """
    Abstract base class for all plate reader file parsers.

    Subclasses must implement:
    - name: Human-readable parser name
    - supported_extensions: List of file extensions this parser handles
    - parse: Main parsing method
    - validate: Check if a file can be parsed by this parser
    - extract_metadata: Extract file metadata (date, instrument, settings)

    Example usage:
        >>> class MyParser(BaseParser):
        ...     @property
        ...     def name(self) -> str:
        ...         return "My Instrument"
        ...
        ...     @property
        ...     def supported_extensions(self) -> List[str]:
        ...         return ['.txt', '.csv']
        ...
        ...     def parse(self, file_path):
        ...         # Parse implementation
        ...         pass
        ...
        ...     def validate(self, file_content):
        ...         # Validation implementation
        ...         pass
        ...
        ...     def extract_metadata(self, file_content):
        ...         # Metadata extraction implementation
        ...         pass
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Human-readable name of the parser/instrument.

        Returns:
            str: Parser name (e.g., "BioTek Synergy HTX")
        """
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """
        List of file extensions supported by this parser.

        Extensions should include the leading dot (e.g., '.txt', '.xlsx').

        Returns:
            List[str]: Supported file extensions
        """
        pass

    @abstractmethod
    def parse(self, file_path: Union[str, Path]) -> Any:
        """
        Parse a plate reader data file.

        Args:
            file_path: Path to the file to parse

        Returns:
            Parsed data object (parser-specific, typically a dataclass)

        Raises:
            ParseError: If the file cannot be parsed
            FileNotFoundError: If the file does not exist
        """
        pass

    @abstractmethod
    def validate(self, file_content: str) -> bool:
        """
        Validate that file content can be parsed by this parser.

        This method is used to auto-detect the appropriate parser
        for a given file. It should be fast and not perform full parsing.

        Args:
            file_content: Raw file content as string

        Returns:
            bool: True if this parser can handle the file
        """
        pass

    @abstractmethod
    def extract_metadata(self, file_content: str) -> Dict[str, Any]:
        """
        Extract metadata from file content.

        Metadata typically includes:
        - reader_type: Instrument model
        - plate_format: 96 or 384 well
        - temperature_setpoint: Temperature setting
        - read_mode: Fluorescence, absorbance, etc.
        - wavelengths: Excitation/emission wavelengths
        - date: Measurement date/time

        Args:
            file_content: Raw file content as string

        Returns:
            Dict[str, Any]: Metadata dictionary
        """
        pass

    def parse_content(self, content: str, format_hint: str = "txt") -> Any:
        """
        Parse file content directly (optional method for uploaded files).

        Default implementation raises NotImplementedError.
        Override in subclasses that support direct content parsing.

        Args:
            content: File content as string
            format_hint: Expected format ('txt', 'csv', etc.)

        Returns:
            Parsed data object
        """
        raise NotImplementedError(
            f"{self.name} parser does not support direct content parsing"
        )

    def can_parse(self, file_path: Union[str, Path]) -> bool:
        """
        Check if this parser can handle the given file.

        Default implementation checks file extension and validates content.

        Args:
            file_path: Path to the file to check

        Returns:
            bool: True if this parser can handle the file
        """
        file_path = Path(file_path)

        # Check extension
        if file_path.suffix.lower() not in self.supported_extensions:
            return False

        # Try to validate content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(4096)  # Read first 4KB for validation
            return self.validate(content)
        except Exception:
            return False

    def __repr__(self) -> str:
        """String representation of the parser."""
        return f"{self.__class__.__name__}(name='{self.name}')"
