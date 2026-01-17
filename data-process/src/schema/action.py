from typing import Any, Dict, List, Optional, Tuple, Union, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Action(BaseModel):
    ...


class Observation(BaseModel):
    pass


class BoundingBox(BaseModel):
    x: float = Field(..., description="The x position of the bounding box")
    y: float = Field(..., description="The y position of the bounding box")
    width: float = Field(..., description="The width of the bounding box")
    height: float = Field(..., description="The height of the bounding box")


class ImageAnnotation(BaseModel):
    text: str = Field(..., description="The text annotation")
    element_type: str = Field(..., description="The type of element")
    bounding_box: BoundingBox = Field(..., description="The boxes of the annotation")


class ImageObservation(Observation):
    class_: str = Field("image_observation", description="The class of the observation")
    content: str = Field(None, description="A path to the image content")
    filename: str = Field(None, description="The filename of the image")
    annotations: list[ImageAnnotation] | None = Field(None, description="The annotations of the image")
    source: str = Field(..., description="The source of the observation (e.g. 'user')")


class TextObservation(Observation):
    class_: str = Field("text_observation", description="The class of the observation")
    content: str = Field(..., description="A textual observation")
    source: str = Field(..., description="The source of the observation (e.g. 'user')")


class ApiAction(Action):
    function: str
    kwargs: dict[str, Any]
    description: str | None = Field(None, description="The description/thought provided for the action")


class CodeAction(Action):
    language: Literal["bash", "python"] = Field(..., description="The language of the code to execute")
    content: str = Field(..., description="The code to execute")
    description: str = Field(..., description="The description/thought provided for the action")


class MessageAction(Action):
    content: str = Field(..., description="The message to share with the user")
    description: str | None = Field(None, description="The description/thought provided for the action")


from enum import Enum
import ast
import inspect


class GUIActionType(str, Enum):
    CLICK = "click"
    DOUBLE_CLICK = "doubleClick"
    RIGHT_CLICK = "rightClick"
    MIDDLE_CLICK = "middleClick"
    MOVE_TO = "moveTo"
    DRAG_TO = "dragTo"
    SCROLL = "scroll"
    HSCROLL = "hscroll"
    WRITE = "write"
    PRESS = "press"
    HOTKEY = "hotkey"


class GUIElement(BaseModel):
    bbox: Optional[Tuple[float, float, float, float]] = Field(
        None, description="The normalized bounding box of the element (x1, y1, x2, y2)"
    )
    pixel_bbox: Optional[Tuple[int, int, int, int]] = Field(
        None, description="The pixel bounding box of the element (x1, y1, x2, y2)"
    )
    image_size: Tuple[int, int] = Field(..., description="The size of the image (width, height)")
    text: Optional[str] = Field(None, description="The text content of the element")

    @model_validator(mode="before")
    @classmethod
    def check_bbox_or_pixel_bbox(cls, values):
        if values.get("bbox") is None and values.get("pixel_bbox") is None:
            raise ValueError("Either 'bbox' or 'pixel_bbox' must be provided")

        if values.get("bbox") is not None and values.get("pixel_bbox") is None:
            bbox = values["bbox"]
            image_size = values["image_size"]
            img_width, img_height = image_size
            x1, y1, x2, y2 = bbox
            values["pixel_bbox"] = (
                round(x1 * img_width),
                round(y1 * img_height),
                round(x2 * img_width),
                round(y2 * img_height),
            )
        elif values.get("pixel_bbox") is not None and values.get("bbox") is None:
            pixel_bbox = values["pixel_bbox"]
            image_size = values["image_size"]
            img_width, img_height = image_size
            x1, y1, x2, y2 = pixel_bbox
            values["bbox"] = (
                x1 / img_width,
                y1 / img_height,
                x2 / img_width,
                y2 / img_height,
            )
        return values

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v):
        if v is not None:
            if not all(0 <= coord <= 1 for coord in v):
                raise ValueError("All bounding box coordinates must be between 0 and 1")
            if v[0] > v[2] or v[1] > v[3]:
                raise ValueError("Invalid bounding box: x1 must be less than x2, and y1 must be less than y2")
        return v

    @field_validator("pixel_bbox")
    @classmethod
    def validate_pixel_bbox(cls, v, info):
        if v is not None:
            image_size = info.data.get("image_size")
            if image_size:
                img_width, img_height = image_size
                if not all(0 <= v[0] <= v[2] <= img_width and 0 <= v[1] <= v[3] <= img_height):
                    raise ValueError("Pixel bounding box coordinates must be within image dimensions")
            if v[0] > v[2] or v[1] > v[3]:
                raise ValueError("Invalid pixel bounding box: x1 must be less than x2, and y1 must be less than y2")
        return v

    @field_validator("image_size")
    @classmethod
    def validate_image_size(cls, v):
        if v[0] <= 0 or v[1] <= 0:
            raise ValueError("Image dimensions must be positive")
        return v

    @property
    def normalized_bbox(self) -> Tuple[float, float, float, float]:
        return self.bbox

    @property
    def absolute_bbox(self) -> Tuple[int, int, int, int]:
        return self.pixel_bbox

    @property
    def center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)


class PyAutoGUIAction(BaseModel):
    action_type: GUIActionType
    target: Optional[GUIElement] = Field(None, description="The target element")
    args: Union[Dict[str, Any], List[Any]] = Field(default_factory=dict, description="Arguments for the action")

    @model_validator(mode="after")
    def initialize_args(self):
        if len(self.args) != 0:
            return self
        if self.action_type == GUIActionType.CLICK:
            self.args = {"x": self.target.center[0], "y": self.target.center[1]}
        elif self.action_type == GUIActionType.WRITE:
            self.args = {"message": self.target.text}
        return self

    @field_validator("args")
    @classmethod
    def validate_args(cls, v):
        if v is not None and "x" in v and "y" in v:
            x, y = v["x"], v["y"]
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError("x and y coordinates must be between 0 and 1")
        return v

    def to_command(self) -> str:
        def convert_and_round(value):
            if isinstance(value, float):
                return round(value, 4)
            return value

        if isinstance(self.args, list):
            args_str = ", ".join(repr(convert_and_round(v)) for v in self.args)
        elif len(self.args) == 1 and next(iter(self.args.keys())) in ["clicks", "amount", "page"]:
            args_str = repr(convert_and_round(next(iter(self.args.values()))))
        else:
            args_str = ", ".join(f"{k}={repr(convert_and_round(v))}" for k, v in self.args.items())
        return f"pyautogui.{self.action_type.value}({args_str})"

    @classmethod
    def from_string(cls, action_string: str) -> "PyAutoGUIAction":
        def _parse_ast_node(node: ast.AST) -> Any:
            if isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.List):
                return [_parse_ast_node(elt) for elt in node.elts]
            elif isinstance(node, ast.Tuple):
                return tuple(_parse_ast_node(elt) for elt in node.elts)
            elif isinstance(node, ast.Dict):
                return { _parse_ast_node(key): _parse_ast_node(value) for key, value in zip(node.keys, node.values) }
            elif isinstance(node, ast.UnaryOp):
                if isinstance(node.op, ast.USub):
                    return -_parse_ast_node(node.operand)
                elif isinstance(node.op, ast.UAdd):
                    return _parse_ast_node(node.operand)
                else:
                    raise TypeError(f"Unsupported unary operator: {type(node.op)}")
            else:
                raise TypeError(f"Unsupported AST node type: {type(node)}")

        tree = ast.parse(action_string)
        call = tree.body[0].value
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute) or getattr(getattr(call.func, 'value', None), 'id', None) != "pyautogui":
            raise ValueError("Invalid PyAutoGUI action string")
        action_type = GUIActionType(call.func.attr)

        # Try to infer kwargs using pyautogui signatures if available, otherwise fallback
        try:
            import pyautogui  # noqa: WPS433
            func = getattr(pyautogui, call.func.attr)
            sig = inspect.signature(func)
            args = [_parse_ast_node(arg) for arg in call.args]
            kwargs = {kw.arg: _parse_ast_node(kw.value) for kw in call.keywords}
            result: Dict[str, Any] = {}
            params = list(sig.parameters.values())
            for i, value in enumerate(args):
                if i < len(params):
                    param = params[i]
                    if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                        result[param.name] = value
                    elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                        result[param.name] = args[i:]
                        break
            result.update(kwargs)
            if len(result) == 1 and "args" in result:
                result = result["args"]
        except Exception as exc:
            # Headless environments may not import pyautogui; use a naive fallback mapping
            if len(call.keywords) > 0:
                result = {kw.arg: _parse_ast_node(kw.value) for kw in call.keywords}
            else:
                # Positional fallback for common 2-arg calls (x,y)
                values = [_parse_ast_node(arg) for arg in call.args]
                if len(values) == 2 and all(isinstance(v, (int, float)) for v in values):
                    result = {"x": values[0], "y": values[1]}
                else:
                    raise RuntimeError("pyautogui unavailable; cannot infer arguments for action string") from exc

        return cls(action_type=action_type, args=result)


class ComputerActionType(str, Enum):
    TRIPLE_CLICK = "tripleClick"
    WAIT = "wait"
    TERMINATE = "terminate"


triple_click_func = {
    "name": "computer.triple_click",
    "description": "Triple click on the screen",
    "parameters": {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "The x coordinate of the triple click"},
            "y": {"type": "number", "description": "The y coordinate of the triple click"},
        },
        "required": ["x", "y"],
    },
}

terminate_func = {
    "name": "computer.terminate",
    "description": "Terminate the current task and report its completion status",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["success", "failure"], "description": "The status of the task"},
        },
        "required": ["status"],
    },
}


class ComputerAction(BaseModel):
    action_type: ComputerActionType
    target: Optional[GUIElement] = Field(None, description="The target element")
    args: Union[Dict[str, Any], List[Any]] = Field(default_factory=dict, description="Arguments for the action")

    @field_validator("args")
    @classmethod
    def validate_args(cls, v):
        if v is not None:
            if "x" in v and "y" in v:
                x, y = v["x"], v["y"]
                if not (0 <= x <= 1 and 0 <= y <= 1):
                    raise ValueError("x and y coordinates must be between 0 and 1")
        return v

    def to_command(self) -> str:
        def convert_and_round(value):
            if isinstance(value, float):
                return round(value, 4)
            if isinstance(value, list):
                return [convert_and_round(v) for v in value]
            return value

        if isinstance(self.args, list):
            args_str = ", ".join(repr(convert_and_round(v)) for v in self.args)
        elif len(self.args) == 1 and next(iter(self.args.keys())) in ["clicks", "amount"]:
            args_str = repr(convert_and_round(next(iter(self.args.values()))))
        else:
            args_str = ", ".join(f"{k}={repr(convert_and_round(v))}" for k, v in self.args.items())
        return f"computer.{self.action_type.value}({args_str})"


class BrowserActionType(str, Enum):
    SELECT_OPTION = "select_option"
    CLEAR = "clear"


class BrowserAction(BaseModel):
    action_type: BrowserActionType
    target: Optional[Any] = Field(None, description="The target element")
    args: Union[Dict[str, Any], List[Any]] = Field(default_factory=dict, description="Arguments for the action")

    def to_command(self) -> str:
        def convert_and_round(value):
            if isinstance(value, float):
                return round(value, 4)
            return value

        if isinstance(self.args, list):
            args_str = ", ".join(repr(convert_and_round(v)) for v in self.args)
        elif len(self.args) == 1 and next(iter(self.args.keys())) in ["clicks", "amount"]:
            args_str = repr(convert_and_round(next(iter(self.args.values()))))
        else:
            args_str = ", ".join(f"{k}={repr(convert_and_round(v))}" for k, v in self.args.items())
        return f"browser.{self.action_type.value}({args_str})"


class MobileActionType(str, Enum):
    Swipe = "swipe"
    Home = "home"
    Back = "back"
    Wait = "wait"
    LongPress = "long_press"
    OpenApp = "open_app"


class MobileAction(BaseModel):
    action_type: MobileActionType
    target: Optional[GUIElement] = Field(None, description="The target element")
    args: Union[Dict[str, Any], List[Any]] = Field(default_factory=dict, description="Arguments for the action")

    @field_validator("args")
    @classmethod
    def validate_args(cls, v):
        if v is not None:
            if "x" in v and "y" in v:
                x, y = v["x"], v["y"]
                if not (0 <= x <= 1 and 0 <= y <= 1):
                    raise ValueError("x and y coordinates must be between 0 and 1")
            elif "from_coord" in v and "to_coord" in v:
                from_coord, to_coord = v["from_coord"], v["to_coord"]
                if not (
                    0 <= from_coord[0] <= 1
                    and 0 <= from_coord[1] <= 1
                    and 0 <= to_coord[0] <= 1
                    and 0 <= to_coord[1] <= 1
                ):
                    raise ValueError("from_coord and to_coord coordinates must be between 0 and 1")
        return v

    def to_command(self) -> str:
        def convert_and_round(value):
            if isinstance(value, float):
                return round(value, 4)
            if isinstance(value, list):
                return [convert_and_round(v) for v in value]
            return value

        if isinstance(self.args, list):
            args_str = ", ".join(repr(convert_and_round(v)) for v in self.args)
        elif len(self.args) == 1 and next(iter(self.args.keys())) in ["clicks", "amount"]:
            args_str = repr(convert_and_round(next(iter(self.args.values()))))
        else:
            args_str = ", ".join(f"{k}={repr(convert_and_round(v))}" for k, v in self.args.items())
        return f"mobile.{self.action_type.value}({args_str})"


class CommunicationActionType(str, Enum):
    ANSWER = "answer"


answer_func = {
    "name": "answer",
    "description": "Answer a question",
    "parameters": {
        "type": "object",
        "properties": {"answer": {"type": "string", "description": "The answer to the question"}},
        "required": ["answer"],
    },
}


class CommunicationAction(BaseModel):
    action_type: CommunicationActionType
    target: Optional[GUIElement] = Field(None, description="The target element")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the action")

    @model_validator(mode="after")
    def validate_args(self):
        if self.action_type == CommunicationActionType.ANSWER and "answer" not in self.args:
            raise ValueError("The 'answer' argument is required for the ANSWER action type")
        return self

    def to_command(self) -> str:
        if self.action_type == CommunicationActionType.ANSWER:
            return f"answer('{self.args['answer']}')"
        else:
            raise ValueError(f"Unsupported action type: {self.action_type}")


class GUIAction(Action):
    observation: Optional[str] = Field(None, description="The observation before the action")
    thought: Optional[str] = Field(None, description="The thought before the action")
    instruction: str = Field(..., description="The description/thought provided for the action")
    guiactions: list[PyAutoGUIAction | BrowserAction | MobileAction | CommunicationAction | ComputerAction] = Field(
        ..., description="The GUI actions to perform"
    )


