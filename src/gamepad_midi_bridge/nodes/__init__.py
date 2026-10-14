"""Node-graph input layer — Phase 1 backend.

Public surface re-exported here so call sites can write:
    from gamepad_midi_bridge.nodes import Node, NodeGraph, Connection
without caring which submodule a type lives in.
"""
from .model import (
    CATEGORIES,
    CategoryMeta,
    Connection,
    ControllerSource,
    InlineTransform,
    Node,
    NodeCategory,
    NodeGraph,
    NodeSpec,
    ParamSpec,
    ParamType,
    PinDirection,
    PinSpec,
    PinValue,
    SourceKind,
    SymbolicSink,
    category_meta,
)
from .evaluator import Send, evaluate
from .registry import NodeRegistry, default_registry, reset_default_registry
from .seed import seed_default_controller_sources

__all__ = [
    "CATEGORIES",
    "CategoryMeta",
    "Connection",
    "ControllerSource",
    "InlineTransform",
    "Node",
    "NodeCategory",
    "NodeGraph",
    "NodeRegistry",
    "NodeSpec",
    "ParamSpec",
    "ParamType",
    "PinDirection",
    "PinSpec",
    "PinValue",
    "Send",
    "SourceKind",
    "SymbolicSink",
    "category_meta",
    "default_registry",
    "evaluate",
    "reset_default_registry",
    "seed_default_controller_sources",
]
