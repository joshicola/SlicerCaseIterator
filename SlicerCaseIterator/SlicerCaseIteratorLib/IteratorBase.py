# =========================================================================
#  Copyright Joost van Griethuysen
#
#  Licensed under the 3-Clause BSD-License (the "License");
#  you may not use this file except in compliance with the License.
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ========================================================================

import slicer
from abc import abstractmethod
import logging

# ------------------------------------------------------------------------------
# IteratorWidgetBase
# ------------------------------------------------------------------------------


class IteratorWidgetBase(object):
    """
    Base class for the GUI subsection controlling the input.

    It defines the GUI elements (via the `setup` function), and controls the starting
    of the batch (`startBatch`, returns an instance derived from IteratorLogicBase).
    Moreover, this class contains functionality to signal or provide information on
    validity of the current config (used to determine whether the user is allowed to
    start the batch) and some functionality to cleanup after a batch is done. Finally,
    this class can respond to the user activating the CaseIterator module and when a
    scene is closed by the user during the iterator over a batch
    (should treated as "cancel the review/updates of this case",
    but not stop the iteration).
    """

    def __init__(self):
        self.logger = logging.getLogger("SlicerCaseIterator.IteratorWidget")
        self.validationHandler = None
        self._iterator = None

    def __del__(self):
        self.logger.debug("Destroying Iterator Widget")
        self.cleanupBatch()

    @abstractmethod
    def setup(self):
        """Setup Group Box containing all the GUI Elements.

        This function should return a qt.QGroupbox containing all the GUI elements
        needed to configure the iterator

        Returns:
            qt.QGroupbox: Group Box containing all of the elements in the input widget.
        """

    def enter(self):
        """
        Function used in subclasses to refresh controls.

        This function is called from the main widget when the user activates the
        CaseIterator module GUI, and can be used to refresh controls
        """
        pass

    def validate(self):
        """Used to validate handlers."""
        if self.validationHandler is not None:
            self.validationHandler(self.is_valid())

    def is_valid(self):
        """Check current configuration for validity.

        This function checks current config to decide whether a batch can be started.
        This is used to enable/disable the "start batch" button.

        Returns:
            boolean: Validity of the current settings.
        """

        return True

    @abstractmethod
    def startBatch(self, reader=None):
        """Start the batch.

        In the derived class, this should store relevant nodes to keep track of
        important data

        Args:
            reader (str, optional): Person reading the batch. Defaults to None.

        Returns:
            IteratorBase: Instance of IteratorBase subclass.
        """

    @abstractmethod
    def cleanupBatch(self):
        """Function to cleanup after finishing or resetting a batch.

        The main objective is to remove non-needed references to tracked nodes in the
        widget, thereby allowing their associated resources to be released and GC'ed.
        """


# ------------------------------------------------------------------------------
# CallbackList
# ------------------------------------------------------------------------------


class IteratorEventListenerList(list):
    """Class to manage case iteration."""

    def __init__(self, iterator):
        super(IteratorEventListenerList, self).__init__()
        self._iterator = iterator

    def caseLoaded(self, *args, **kwargs):
        """Perform when a case is loaded."""
        for eventListener in self:
            eventListener.onCaseLoaded(self._iterator, *args, **kwargs)

    def caseAboutToClose(self, *args, **kwargs):
        """Perform before a case is closed."""
        for eventListener in self:
            eventListener.onCaseAboutToClose(self._iterator, *args, **kwargs)


# ------------------------------------------------------------------------------
# IteratorLogicBase
# ------------------------------------------------------------------------------


class IteratorLogicBase(object):
    """
    Base class for the iterator object.

    An instance of a class derived from this class is returned by the corresponding
    widget's startBatch function. 3 attributes are accessed from the CaseIteratorLogic:

    - caseCount: Integer specifying how many cases are present in the batch defined by
                 this iterator
    - loadCase: Function to load a certain case, specified by the passed `case_idx`
    - closeCase: Function called by the logic to close currently opened case
    - saveMask: Function to store a loaded or new mask.
    """

    @property
    def parameterNode(self):
        """A node to store relevant iterator and case parameters within.

        If a parameter node does not exist, it is created.

        Returns:
            vtkMRMLScriptedModuleNode: The retrieved or created parameter node.
        """
        node = self._findParameterNodeInScene()
        if not node:
            node = self._createParameterNode()
        return node

    @staticmethod
    def removeNodeByID(nodeID, mrmlScene=slicer.mrmlScene):
        """Remove node from Slicer Scene by Node ID.

        Args:
            nodeID (str): ID of the Node to delete.
            mrmlScene (vtkMRMLScene, optional): Slicer Scene.
                                                Defaults to slicer.mrmlScene.
        """
        node = mrmlScene.GetNodeByID(nodeID)
        if node:
            mrmlScene.RemoveNode(node)

    def __init__(self):
        self.logger = logging.getLogger("SlicerCaseIterator.Iterator")
        self.currentIdx = None
        self.caseCount = None
        self._eventListeners = IteratorEventListenerList(self)

    def __del__(self):
        self.logger.debug("Destroying Case Iterator Logic instance")
        if self.currentIdx is not None:
            self.closeCase()
        self._eventListeners = []
        slicer.mrmlScene.RemoveNode(self.parameterNode)

    def _findParameterNodeInScene(self):
        """Find and return the parameter node.

        If the parameter node is not found, return None.

        Returns:
            vtkMRMLScriptedModuleNode or None: The parameter node or None.
        """
        for i in range(
            slicer.mrmlScene.GetNumberOfNodesByClass("vtkMRMLScriptedModuleNode")
        ):
            n = slicer.mrmlScene.GetNthNodeByClass(i, "vtkMRMLScriptedModuleNode")
            if n.GetModuleName() == "SlicerCaseIterator":
                return n
        return None

    def _createParameterNode(self):
        """Create a parameter node for the batch.

        Returns:
            vtkMRMLScriptedModuleNode: An instantiated parameter node.
        """
        node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScriptedModuleNode")
        node.SetSingletonTag("SlicerCaseIterator")
        node.SetModuleName("SlicerCaseIterator")
        return node

    def registerEventListener(self, listener):
        """Registering a listener that can act upon event invocation.

        Implementations of IteratorLogicBase have to call
        self._eventListeners.caseLoaded(parameterNode) or
        self._eventListeners.caseAboutToClose(parameterNode)

        Args:
            listener (IteratorEventHandlerBase): Subclass of IteratorEventHandlerBase
        """

        if listener not in self._eventListeners:
            self._eventListeners.append(listener)

    @abstractmethod
    def loadCase(self, case_idx):
        """Function called to load the next desired case.

        The logic to load the next desired case, as specified by the case_idx.

        Args:
            case_idx (int): index of the next case to load,
                            0 <= case_idx < self.caseCount

        Returns:
            tuple: The loaded images, (main_image, main_mask,
                   list of additional images, list of additional masks)
        """

    @abstractmethod
    def closeCase(self):
        """Function called by the logic to close currently opened case."""

    @abstractmethod
    def getCaseData(self):
        """
        Return the nodes of the current case.

        Implementations for the iterator have to provide this method so
        e.g. event listeners can work with its loaded data

        Returns:
            tuple: The loaded images, (main_image, main_mask,
                   list of additional images, list of additional masks)
        """


class IteratorEventHandlerBase(object):
    """Base class for event based handlers that can listen to events of
    IteratorLogicBase implementations"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def onCaseLoaded(self, caller, *args, **kwargs):
        pass

    @abstractmethod
    def onCaseAboutToClose(self, caller, *args, **kwargs):
        pass
