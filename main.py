"""
链科云打印盒MCP服务器

提供云打印盒操作打印机的MCP接口，包括：
- 获取打印机列表
- 提交打印任务
- 查询任务状态
- 获取设备信息
- 打印机状态查询等功能

使用方法:
    uv run main.py
"""
import io
import logging
import os
import json
import mimetypes
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional, Union, AsyncIterator
from dataclasses import dataclass

from mcp import ServerSession
from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field

from lianke_printing import LiankePrinting
from lianke_printing.exceptions import LiankePrintingException

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_lianke_client(api_key: str, device_id: str, device_key: str) -> LiankePrinting:
    """创建 LiankePrinting 客户端实例"""
    if not api_key or not device_id or not device_key:
        raise ValueError("API密钥、设备ID和设备密钥不能为空")
    
    return LiankePrinting(api_key, device_id, device_key)


# 创建MCP服务器
mcp = FastMCP("LiankePrintBox",
              website_url="https://www.liankenet.com")


@mcp.tool()
def get_device_info(
    ctx: Context,
    device_id: Optional[str] = None, 
    device_key: Optional[str] = None,
) -> Dict[str, Any]:
    """获取设备信息"""
    headers = ctx.request_context.request.headers
    api_key = headers.get("ApiKey")
    device_id = headers.get("DeviceId") or device_id
    device_key = headers.get("DeviceKey") or device_key
    
    if not api_key:
        return {"code": 400, "msg": "请求头中缺少 ApiKey"}
        
    client = create_lianke_client(api_key, device_id, device_key)
    result = client.device_info()
    return result


@mcp.tool()
def get_printer_list(
    ctx: Context,
    device_id: Optional[str] = None, 
    device_key: Optional[str] = None, 
    printer_type: int = 1
) -> Dict[str, Any]:
    """
    获取设备打印机列表
    
    Args:
        device_id: 设备ID（可选，未提供时使用默认配置）
        device_key: 设备密钥（可选，未提供时使用默认配置）
        printer_type: 打印机类型 1=USB打印机 2=网络打印机 3=USB和网络打印机
    
    Returns:
        打印机列表信息，包含打印机型号、端口、状态等
    """
    headers = ctx.request_context.request.headers
    print("ApiKey", headers.get("ApiKey"))

    try:
        # 从请求头获取配置信息
        api_key = headers.get("ApiKey")
        device_id = headers.get("DeviceId") or device_id
        device_key = headers.get("DeviceKey") or device_key
        
        if not api_key:
            return {"code": 400, "msg": "请求头中缺少 ApiKey"}
        
        # 创建客户端
        client = create_lianke_client(api_key, device_id, device_key)
        
        # 获取打印机列表
        result = client.printer_list(printer_type)
        printers = result.get("data", {}).get("row", [])
        
        return {
            "code": 200,
            "msg": "success",
            "data": {
                "printers": printers,
                "total": len(printers)
            }
        }
    except LiankePrintingException as e:
        return {"code": e.code or 503, "msg": e.msg}
    except ValueError as e:
        return {"code": 400, "msg": str(e)}
    except Exception as e:
        logger.error(f"获取打印机列表失败: {e}")
        return {"code": 503, "msg": f"获取打印机列表失败: {str(e)}"}


def get_default_printer(api_key: str, device_id: str, device_key: str):
    """获取默认打印机"""
    try:
        client = create_lianke_client(api_key, device_id, device_key)
        result = client.printer_list(1)  # USB打印机
        printers = result.get("data", {}).get("row", [])
        if not printers:
            return None
        # 默认取第一个
        printer_hash = printers[0]["hash_id"]
        return printer_hash
    except Exception as e:
        logger.error(f"获取默认打印机失败: {e}")
        return None


@mcp.tool()
def get_printer_params(
    ctx: Context,
    printer_hash: str, 
    device_id: Optional[str] = None, 
    device_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取打印机参数配置
    
    Args:
        printer_hash: 打印机哈希ID
        device_id: 设备ID（可选，未提供时从请求头获取）
        device_key: 设备密钥（可选，未提供时从请求头获取）
    
    Returns:
        打印机参数配置，包含纸张尺寸、颜色、双面打印等选项
    """
    headers = ctx.request_context.request.headers
    
    try:
        # 从请求头获取配置信息
        api_key = headers.get("ApiKey")
        device_id = headers.get("DeviceId") or device_id
        device_key = headers.get("DeviceKey") or device_key
        
        if not api_key:
            return {"code": 400, "msg": "请求头中缺少 ApiKey"}
        
        # 创建客户端
        client = create_lianke_client(api_key, device_id, device_key)
        
        # 获取打印机参数
        result = client.printer_params(printer_hash)
        return {
            "code": 200,
            "msg": "success",
            "data": result.get("data", {})
        }
    except LiankePrintingException as e:
        return {"code": e.code or 503, "msg": e.msg}
    except ValueError as e:
        return {"code": 400, "msg": str(e)}
    except Exception as e:
        logger.error(f"获取打印机参数失败: {e}")
        return {"code": 503, "msg": f"获取打印机参数失败: {str(e)}"}


@mcp.tool()
def submit_print_job(
    ctx: Context,
    job_file_url: str,
    kwargs: str,
    device_id: Optional[str] = None,
    device_key: Optional[str] = None,
    hash_id: Optional[str] = None,
    dm_paper_size: str = "9",  # A4
    jp_scale: str = "fit",  # 自适应
    dm_orientation: str = "1",  # 竖向
    dm_copies: str = "1",  # 打印1份
    dm_color: str = "1"  # 黑白
) -> Dict[str, Any]:
    """
    提交打印任务
    
    Args:
        job_file_url: 打印文件URL（支持图片、PDF、Office文档等）
        kwargs: 其他打印参数（JSON字符串格式）
        device_id: 设备ID（可选，未提供时使用环境变量）
        device_key: 设备密钥（可选，未提供时使用环境变量）
        hash_id: 打印机hash_id
        dm_paper_size: 纸张尺寸（9=A4, 11=A5）
        jp_scale: 自动缩放（fit=自适应, fitw=宽度优先, fith=高度优先, fill=拉伸, cover=铺满, none=关闭）
        dm_orientation: 纸张方向（1=竖向, 2=横向）
        dm_copies: 打印份数
        dm_color: 打印颜色（1=黑白, 2=彩色）
    
    Returns:
        任务提交结果，包含task_id用于后续查询
    """
    headers = ctx.request_context.request.headers
    
    try:
        # 从请求头获取配置信息
        api_key = headers.get("ApiKey")
        device_id = headers.get("DeviceId") or device_id
        device_key = headers.get("DeviceKey") or device_key
        
        if not api_key:
            return {"code": 400, "msg": "请求头中缺少 ApiKey"}

        if not hash_id:
            hash_id = get_default_printer(api_key, device_id, device_key)
            if not hash_id:
                return {"code": 404, "msg": "打印未连接"}

        # 创建客户端
        client = create_lianke_client(api_key, device_id, device_key)
        
        # 构建打印任务参数
        job_params = {
            "dmPaperSize": int(dm_paper_size),
            "jpScale": jp_scale,
            "dmOrientation": int(dm_orientation),
            "dmCopies": int(dm_copies),
            "dmColor": int(dm_color),
        }
        
        # 添加额外参数（如果提供了kwargs）
        if kwargs:
            try:
                extra_params = json.loads(kwargs)
                job_params.update(extra_params)
            except json.JSONDecodeError:
                logger.warning(f"无法解析kwargs参数: {kwargs}")
                # 如果不是JSON格式，尝试作为简单的键值对处理
                if "=" in kwargs:
                    pairs = kwargs.split(",")
                    for pair in pairs:
                        if "=" in pair:
                            key, value = pair.split("=", 1)
                            job_params[key.strip()] = value.strip()
        
        # 准备文件数据
        import requests
        try:
            file_response = requests.get(job_file_url, timeout=30)
            file_response.raise_for_status()
            file_content = file_response.content
            filename = job_file_url.split('/')[-1] or 'document.pdf'
            
            # 获取文件MIME类型
            mimetype, _ = mimetypes.guess_type(job_file_url)
            if not mimetype:
                mimetype = 'application/octet-stream'
            
            # 准备文件上传
            job_files = [("jobFile", (filename, io.BytesIO(file_content), mimetype))]
            
            # 提交打印任务
            result = client.add_job(job_files, hash_id, **job_params)
            return result
            
        except requests.RequestException as e:
            logger.error(f"下载文件失败: {e}")
            return {"code": 400, "msg": f"下载文件失败: {str(e)}"}
        
    except LiankePrintingException as e:
        return {"code": e.code or 503, "msg": e.msg}
    except ValueError as e:
        return {"code": 400, "msg": str(e)}
    except Exception as e:
        logger.error(f"提交打印任务失败: {e}")
        return {"code": 503, "msg": f"提交打印任务失败: {str(e)}"}


@mcp.tool()
def submit_print_job_with_file(
    ctx: Context,
    file_path: str,
    printer_hash: Optional[str] = None,
    kwargs: str = "{}",
    device_id: Optional[str] = None,
    device_key: Optional[str] = None,
    dm_paper_size: str = "9",  # A4
    jp_scale: str = "fit",  # 自适应
    dm_orientation: str = "1",  # 竖向
    dm_copies: str = "1",  # 打印1份
    dm_color: str = "1"  # 黑白
) -> Dict[str, Any]:
    """
    从本地文件提交打印任务（支持从MCP读取文件）
    
    Args:
        file_path: 本地文件路径（相对或绝对路径）
        kwargs: 其他打印参数（JSON字符串格式）
        device_id: 设备ID（可选，未提供时使用环境变量）
        device_key: 设备密钥（可选，未提供时使用环境变量）
        printer_hash: 打印机ID
        dm_paper_size: 纸张尺寸（9=A4, 11=A5）
        jp_scale: 自动缩放（fit=自适应, fitw=宽度优先, fith=高度优先, fill=拉伸, cover=铺满, none=关闭）
        dm_orientation: 纸张方向（1=竖向, 2=横向）
        dm_copies: 打印份数
        dm_color: 打印颜色（1=黑白, 2=彩色）
    
    Returns:
        任务提交结果，包含task_id用于后续查询
    """
    headers = ctx.request_context.request.headers
    
    try:
        # 从请求头获取配置信息
        api_key = headers.get("ApiKey")
        device_id = headers.get("DeviceId") or device_id
        device_key = headers.get("DeviceKey") or device_key
        
        if not api_key:
            return {"code": 400, "msg": "请求头中缺少 ApiKey"}

        if not printer_hash:
            printer_hash = get_default_printer(api_key, device_id, device_key)
            if not printer_hash:
                return {"code": 404, "msg": "打印未连接"}

        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {"code": 400, "msg": f"文件不存在: {file_path}"}

        # 读取文件内容
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
        except Exception as e:
            return {"code": 400, "msg": f"读取文件失败: {str(e)}"}

        # 获取文件信息
        filename = os.path.basename(file_path)
        mimetype, _ = mimetypes.guess_type(file_path)
        if not mimetype:
            # 根据文件扩展名设置默认MIME类型
            ext = os.path.splitext(filename)[1].lower()
            mimetype_map = {
                '.pdf': 'application/pdf',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.xls': 'application/vnd.ms-excel',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.ppt': 'application/vnd.ms-powerpoint',
                '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                '.txt': 'text/plain'
            }
            mimetype = mimetype_map.get(ext, 'application/octet-stream')

        # 创建客户端
        client = create_lianke_client(api_key, device_id, device_key)
        
        # 准备文件上传
        job_files = [("jobFile", (filename, io.BytesIO(file_content), mimetype))]

        # 构建打印任务参数
        job_params = {
            "dmPaperSize": int(dm_paper_size),
            "jpScale": jp_scale,
            "dmOrientation": int(dm_orientation),
            "dmCopies": int(dm_copies),
            "dmColor": int(dm_color),
        }
        
        # 添加额外参数（如果提供了kwargs）
        if kwargs:
            import json
            try:
                extra_params = json.loads(kwargs)
                job_params.update(extra_params)
            except json.JSONDecodeError:
                logger.warning(f"无法解析kwargs参数: {kwargs}")
                # 如果不是JSON格式，尝试作为简单的键值对处理
                if "=" in kwargs:
                    pairs = kwargs.split(",")
                    for pair in pairs:
                        if "=" in pair:
                            key, value = pair.split("=", 1)
                            job_params[key.strip()] = value.strip()
        
        # 提交打印任务
        result = client.add_job(job_files, printer_hash, **job_params)
        return result
        
    except LiankePrintingException as e:
        return {"code": e.code or 503, "msg": e.msg}
    except ValueError as e:
        return {"code": 400, "msg": str(e)}
    except Exception as e:
        logger.error(f"提交打印任务失败: {e}")
        return {"code": 503, "msg": f"提交打印任务失败: {str(e)}"}


@mcp.tool()
def get_job_status(
    ctx: Context,
    task_id: str,
    device_id: Optional[str] = None,
    device_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    查询打印任务状态
    
    Args:
        task_id: 任务ID（提交任务时返回的task_id）
        device_id: 设备ID（可选，未提供时使用环境变量）
        device_key: 设备密钥（可选，未提供时使用环境变量）
        device_port: 设备端口（可选，未提供时使用环境变量）
    
    Returns:
        任务状态信息，包含任务状态、打印结果等
    """
    headers = ctx.request_context.request.headers
    
    try:
        # 从请求头获取配置信息
        api_key = headers.get("ApiKey")
        device_id = headers.get("DeviceId") or device_id
        device_key = headers.get("DeviceKey") or device_key
        
        if not api_key:
            return {"code": 400, "msg": "请求头中缺少 ApiKey"}
        
        # 创建客户端
        client = create_lianke_client(api_key, device_id, device_key)
        
        # 查询任务状态
        result = client.job_result(task_id)
        return result
        
    except LiankePrintingException as e:
        return {"code": e.code or 503, "msg": e.msg}
    except ValueError as e:
        return {"code": 400, "msg": str(e)}
    except Exception as e:
        logger.error(f"查询任务状态失败: {e}")
        return {"code": 503, "msg": f"查询任务状态失败: {str(e)}"}


@mcp.tool()
def cancel_print_job(
    ctx: Context,
    task_id: str,
    device_id: Optional[str] = None,
    device_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    取消打印任务
    
    Args:
        task_id: 任务ID
        device_id: 设备ID（可选，未提供时使用环境变量）
        device_key: 设备密钥（可选，未提供时使用环境变量）

    Returns:
        取消结果
    """
    headers = ctx.request_context.request.headers
    
    try:
        # 从请求头获取配置信息
        api_key = headers.get("ApiKey")
        device_id = headers.get("DeviceId") or device_id
        device_key = headers.get("DeviceKey") or device_key
        
        if not api_key:
            return {"code": 400, "msg": "请求头中缺少 ApiKey"}
        
        # 创建客户端
        client = create_lianke_client(api_key, device_id, device_key)
        
        # 取消任务
        result = client.cancel_job(task_id)
        return result
        
    except LiankePrintingException as e:
        return {"code": e.code or 503, "msg": e.msg}
    except ValueError as e:
        return {"code": 400, "msg": str(e)}
    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        return {"code": 503, "msg": f"取消任务失败: {str(e)}"}


@mcp.tool()
def get_printer_status(
    ctx: Context,
    printer_hash: str, 
    device_id: Optional[str] = None, 
    device_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取打印机实时状态
    
    Args:
        printer_hash: 打印机唯一id
        device_id: 设备ID（可选，未提供时使用环境变量）
        device_key: 设备密钥（可选，未提供时使用环境变量）
    
    Returns:
        打印机状态信息，包含缺纸、卡纸、盖子状态等
    """
    headers = ctx.request_context.request.headers
    
    try:
        # 从请求头获取配置信息
        api_key = headers.get("ApiKey")
        device_id = headers.get("DeviceId") or device_id
        device_key = headers.get("DeviceKey") or device_key
        
        if not api_key:
            return {"code": 400, "msg": "请求头中缺少 ApiKey"}
        
        # 创建客户端
        client = create_lianke_client(api_key, device_id, device_key)
        
        # 获取打印机状态
        result = client.printer_status(printer_hash)
        if result is None:
            return {"code": 503, "msg": "获取打印机状态失败"}
        return result
        
    except LiankePrintingException as e:
        return {"code": e.code or 503, "msg": e.msg}
    except ValueError as e:
        return {"code": 400, "msg": str(e)}
    except Exception as e:
        logger.error(f"获取打印机状态失败: {e}")
        return {"code": 503, "msg": f"获取打印机状态失败: {str(e)}"}


# 添加提示模板
@mcp.prompt()
def print_job_prompt(
    file_url: str,
    paper_size: str = "A4",
    copies: int = 1,
    color: str = "黑白"
) -> str:
    """生成打印任务提示"""
    return f"""
请帮我提交一个打印任务：
- 文件URL: {file_url}
- 纸张尺寸: {paper_size}
- 打印份数: {copies}
- 打印颜色: {color}

请确认设备ID和设备密钥已正确配置，然后提交打印任务。
"""


@mcp.prompt()
def device_setup_prompt(device_id: str = "", device_key: str = "") -> str:
    """生成设备配置提示"""
    return f"""
链科云打印盒设备配置：

1. 设备ID: {device_id or '请从二维码获取'}
2. 设备密钥: {device_key or '请从二维码获取'}
3. API密钥: 请通过请求头 ApiKey 提供

配置步骤：
1. 扫描设备二维码获取deviceId和deviceKey
2. 到开放平台(https://open.liankenet.com/)注册获取ApiKey
3. 在请求头中设置 ApiKey、DeviceId、DeviceKey
4. 使用get_printer_list工具获取打印机列表
5. 使用submit_print_job工具提交打印任务

注意事项：
1. printer_list的hash_id为printerHash
2. 所有配置信息都通过请求头传递，不再使用环境变量
"""

if __name__ == '__main__':
    mcp.run(transport="streamable-http")
