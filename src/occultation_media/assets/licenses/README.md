# Occultation Media — 独立掩星动画生成器

独立的 Python 桌面工具，与 SatOccult 无关，不依赖 Codex 技能或个人文件路径。
选择观测文件和 Tangra CSV 后，输出同步星场＋光变曲线 GIF、PNG 和可选 MP4。

## 普通用户

- **Mac**：解压 `OccultationMedia-macOS-Intel.zip`，打开 `OccultationMedia.app`。
  此构建要求 macOS 14 或以上；Intel Mac 原生运行，Apple Silicon 需要 Rosetta。
  包含 Python、中文字体、FFmpeg 和 ADV 解码库，不需要另装 Python。
- **Windows**：解压 Windows 构建生成的 `OccultationMedia-Windows-x64.zip`，
  保留整个文件夹，双击其中的 `OccultationMedia.exe`。目标为 Windows 10/11 x64。
  Windows 发布包必须在 Windows 构建；本次 Mac 环境不能代替 Windows 实机验证。
- 当前是本地开发构建，没有 Apple Developer 公证或 Windows 发布者签名。

### 使用步骤

1. 选择 `.adv` / `.ser` / `.fit` / `.fits` / `.fts` / `.ravf` / `.lc`；
   多张 FITS 使用“FITS 文件夹”。
2. 选择 Tangra 测光 CSV 和输出文件夹。
3. 填写事件日期、曝光毫秒、小行星和恒星名称。预报 UTC 和误差可留空。
4. 核实“源第 0 帧对应的 CSV 帧号”：视频第一帧若对应 CSV 1500，就填 1500。
   程序按 `源索引 = CSV帧号 − 该值` 对齐。LC 模式直接使用内部帧号。
5. 选择输出语言：`both` 中英文、`zh` 中文、`en` 英文；点击“生成动画”。
6. “打开结果文件夹”查看结果。每次生成新子文件夹，不覆盖上一批结果。

可选项：低光通量首末帧号可绕过自动检测；目标 X Y 是原始图像左上角为原点、
从零开始的固定像素坐标。不填写时自动读取 CSV 中被掩目标的 StartingX/StartingY；手动填写优先。CSV 缺失有效坐标时不画指针。源文件须与 CSV 使用相同裁切和方向。当前没有逐帧质心追踪。
关闭窗口或点击取消会终止生成进程，已生成的部分文件和日志会保留。

## 科学与格式约定

- 初始**显示帧**的 0.5% / 99.95% 分位数确定黑白点，整段固定；
  `gray=round(255*asinh(8*clip((p-black)/(white-black),0,1))/asinh(8))`。
- 星场保留完整范围和原始方向；LC 提供 35×35 切片。Bayer 数据显示原始灰度样本。
- 曲线是 Tangra `Signal − Background`，不会从显示拉伸后的图像测光。
- CSV UTC 控制显示和播放时长；原文件时间另存元数据，不重复进行采集延迟校正。
- GIF 帧时长以 10 ms 为单位；高帧率数据可用“每 N 帧显示一帧”降低显示帧率。
- 自动检测是可视化估计，不能用于正式 D/R 报告。短事件可填明确的低光通量帧范围。
- ADV 支持 **ADV2 主视频流**，不支持 ADV1。
- SER 支持 1–16 位、mono/Bayer/RGB/BGR。默认按头部字节序读取；部分软件标志相反，
  可选 `little` 或 `big`。已知 FY22 PIPP 示例需要 `little`。
- FITS 支持二维图、三维 `(time,y,x)` 数据立方或自然文件名排序的序列，保留 BSCALE/BZERO。
  多图像 HDU 文件需填写 HDU 编号。三维文件按时间立方解释，不按彩色图解释。
- RAVF 支持 8/16 位及 packed/unpacked 10/12 位，保留计数、不自动提升到 16 位。
  packed 10 位每行宽度须为 4 的倍数，packed 12 位须为 2 的倍数。
- 仍要求 Tangra CSV；不是自动测光软件。缺失目标测光、重复帧号、非递增时间会报错。

## 开发者：脚本运行与打包

建议 Python 3.13（python.org，含 Tk）。

```bash
python -m venv .venv
# 激活环境后：
python -m pip install -e ".[build]"
python launch.py                       # 桌面窗口
python launch.py --cli --help          # 命令行参数
python -m unittest discover -s tests -v
python launch.py --self-test report.json
```

Mac：双击 `Build-Mac.command`，使用 python.org 的 universal2/Intel Python。
脚本只将项目自己的临时构建环境转为 x86_64，不修改系统 Python。Apple Silicon 需 Rosetta。
Windows：安装 Python 3.13 x64 后双击 `Build-Windows.bat`。
二者都运行测试、PyInstaller、封装后自检，然后在 `dist/` 生成 ZIP。
也可以使用 `.github/workflows/build-desktop.yml` 在指定的 GitHub 仓库内手动触发构建。
这里提供工作流文件；不会自动创建仓库、推送代码或发布。

封装程序支持 `--self-test <报告路径>`，测试 bundled 字体、SER/FITS/RAVF、中英文 GIF/MP4。
ADV 需要另用真实录像验证。Windows GUI 子进程通过 job/result JSON 通信，不依赖控制台标准流。
输出目录中的 `job.json`、`run.log`、`result.json` 和 `occultation_metadata.json` 保留运行信息。

## 代码结构

- `src/occultation_media/read_*`：文件读取。
- `detect_low_flux.py`：可视化事件区间判据。
- `prepare_source_frames.py`、`make_tangra_occultation_media.py`：同步与运行流程。
- `render_*`：固定拉伸、图像布局、导出。
- `desktop_*`、`launcher.py`：跨平台界面和独立任务进程。
- `build_tools/`、`OccultationMedia.spec`：两平台原生打包。
- `tests/`：格式、时序、拉伸、端到端测试。

版本以 `pyproject.toml` 为准。布局渲染模块约 230 行，因为两种语言共用同一帧的紧密关联面板；
其余模块按职责拆分。第三方许可证见 `THIRD_PARTY.md` 和字体随附的 OFL。

Mac 构建还需要 Xcode Command Line Tools（提供 `lipo`）；这只影响开发者打包，不影响使用发布包。
中文输入法的全角数字、冒号和逗号会在数字参数中自动规范化，文件路径和目标名称保持原样。

## v1.1.0：界面语言

窗口右上角的“界面语言 / Interface”可即时切换中文和 English。
切换保留全部输入、输出选项和正在运行的任务；“动画输出语言”独立控制生成文件。
表单、按钮、选择框、状态和输入校验提示随界面切换。系统文件对话框的系统按钮
遵循操作系统语言；底层解码器的原始诊断日志保留英文，便于排错。

## v1.2.0：可选预报

- 预报时刻留空：完全省略预报蓝色带、中心线、图例和说明；误差框即使有旧值也不使用。
- 只填预报时刻：显示中心线与时刻，不显示误差带或 ± 数字。
- 时刻和误差都填：显示中心线及蓝色误差区间。误差可以为 0。
- 没有预报时，自动检测搜索整段 CSV；不会拿实测中点冒充预报。
  自动检测至少需要 31 个采样点；未找到区间或短片段时请填写首末低光通量帧号。
- 命令行同样可以省略 `--predicted-time` 和 `--prediction-error-sec`；元数据中缺失预报记为 null。

## v1.3.0：自动目标标记

全星场模式默认从 Tangra CSV 读取被掩目标的初始坐标。手动坐标优先，输出元数据记录坐标来源。适用于 ADV/SER/FITS/RAVF；固定位置不会随漂移跟踪。

## v1.3.1：星点标记样式

黄色十字定位标记只保留下方与右侧两条线，中心留空以免遮挡目标星。
