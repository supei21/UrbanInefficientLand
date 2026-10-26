"""智能体可自主调用的业务工具。"""

__all__ = ["build_block_tools", "build_landscape_tools"]


def __getattr__(name: str):
    if name == "build_block_tools":
        from tianshu_core.tools.block_tools import build_block_tools

        return build_block_tools
    if name == "build_landscape_tools":
        from tianshu_core.tools.landscape_tools import build_landscape_tools

        return build_landscape_tools
    raise AttributeError(name)
