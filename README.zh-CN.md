# OccultationMedia

[English](README.md) | **简体中文**

桌面掩星动画生成器：将观测星场与 Tangra 光变曲线同步，导出 GIF、PNG 和 MP4。支持中文 / English 界面。

## 下载与使用

从 [Releases](https://github.com/hjs12345678900/OccultationMedia/releases/latest) 下载：

- **Windows 10/11 x64**：完整解压后打开 `OccultationMedia.exe`，保留 `_internal` 文件夹。
- **macOS 14+**：解压后打开 `OccultationMedia.app`。Intel 版；Apple Silicon 需要 Rosetta。

选择观测文件、Tangra CSV 和输出目录，填写日期、曝光时间及目标名称，点击生成。预报时间和区间可留空。

## 功能

- 输入：ADV2、SER、FITS 图像 / 序列 / 数据立方、RAVF，以及 Tangra LC 星点切片。
- 使用 Tangra CSV 测光与 UTC；填写源文件第 0 帧对应的 CSV 帧号以对齐。
- 自动读取 CSV 目标初始坐标，支持手动覆盖；标记仅右侧和下方两条线，不做逐帧跟踪。
- 首个显示帧的 0.5% / 99.95% 分位数确定固定拉伸，整段保持一致。
- 可选中英文输出，内置中文字体、Python 和 FFmpeg。

本工具用于动画展示，不用于正式掩星时刻测量。v1.3.2 发布包未签名 / 公证；仅完成打包和文件检查，未进行该版本的运行测试。

## 源码运行与打包

使用包含 Tk 的 Python 3.13，在虚拟环境中执行：

```bash
python -m pip install -e ".[build]"
python launch.py
```

Windows 打包入口：`Build-Windows.bat`；Mac：`Build-Mac.command`。两者包含测试。
仅打包 Windows：`python package_windows_only.py`；仅打包 Mac：`python -m PyInstaller --noconfirm --clean OccultationMedia.spec`。
GitHub Actions 仅手动触发。第三方组件与许可见 [THIRD_PARTY.md](THIRD_PARTY.md)。
