from . import CsvTableIterator
from . import CsvInferenceIterator
from . import IteratorBase
from functools import wraps
import logging


def onExceptionReturnNone(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (IndexError, AttributeError, KeyError) as exc:
            logging.error(exc)
            return None

    return wrapper


class IteratorFactory(object):
    """Class to create iterator widgets."""

    IMPLEMENTATIONS = {
        "simple_csv_iteration": CsvTableIterator.CaseTableIteratorWidget,
        "mask_comparison": CsvInferenceIterator.CsvInferenceIteratorWidget,
    }

    @classmethod
    def registerIteratorWidget(cls, name, widget):
        """Register a new instatiated widget under IMPLEMENTATIONS.

        This function would be used to dynamically create a new implementation.

        Args:
            name (str): Key of IMPLEMENTATIONS.
            widget (IteratorBase.IteratorWidgetBase): Subclass of the IteratorWidgetBase.
        """
        if name in cls.IMPLEMENTATIONS.keys():
            logging.warning(f"Iterator {name} is already registered")
            return
        if not issubclass(widget, IteratorBase.IteratorWidgetBase):
            logging.warning(
                f"Widget {widget} is no subclass of IteratorBase.IteratorWidgetBase"
            )
            return
        cls.IMPLEMENTATIONS[name] = widget

    @staticmethod
    def reloadSourceFiles():
        """Reload all required modules."""
        packageName = "SlicerCaseIteratorLib"
        submoduleNames = [
            "IteratorBase",
            "CsvTableIterator",
            "CsvInferenceIterator",
            "IteratorFactory",
        ]
        import imp

        f, filename, description = imp.find_module(packageName)
        package = imp.load_module(packageName, f, filename, description)
        for submoduleName in submoduleNames:
            f, filename, description = imp.find_module(submoduleName, package.__path__)
            try:
                imp.load_module(
                    packageName + "." + submoduleName, f, filename, description
                )
            finally:
                f.close()

    @staticmethod
    def getImplementationNames():
        """Get the names of the implementations.

        Returns:
            list: List of valid implementations.
        """
        return list(IteratorFactory.IMPLEMENTATIONS.keys())

    @staticmethod
    @onExceptionReturnNone
    def getIteratorWidget(mode):
        """Get the Iterator Widget specified by "mode".

        Args:
            mode (str): The key of the Iterator Widget to retrieve.

        Returns:
            IteratorBase.IteratorWidgetBase: Instatiated subclass of IteratorWidgetBase.
        """
        return IteratorFactory.IMPLEMENTATIONS[mode]
