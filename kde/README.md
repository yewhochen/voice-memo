# 随口记 · Voice Note

轻量本地录音工具，使用系统 Python/PyQt6、PulseAudio（PipeWire 兼容）和 ffmpeg。无账号，无上传。

## 启动

```bash
/usr/bin/python3 app.py
# 只显示托盘
/usr/bin/python3 app.py --tray
```

也可以在 KDE 应用菜单搜索「随口记」。

## 操作

- 窗口可见即预览真实麦克风电平（不写音频文件）；隐藏后停止预览。
- `Start` 开始录音，录制期间按钮显示时长，再次点击停止、自动保存并发送桌面通知。
- `Setting` 位于录音按钮下，选择麦克风与 WAV / FLAC / MP3，自动记住选择。
- `History` 显示最近五条有效录音；悬停显示 Play / Copy / Delete：默认播放器、文件复制到剪贴板、确认后移至回收站。
- 右下角文件夹按钮打开录音目录；主界面不显示保存路径。
- 托盘单击显示/收起。关闭或收起结束当前会话：录音安全保存后清空界面状态；音频、设置和失败时可恢复原始录音保留。右键可退出。
- 未设置开机自启；M15 版本和本机数据相互独立。

## 数据位置

- 录音：`~/Music/Voice Notes/`
- 设置：`~/.config/Nous/VoiceNote.conf`
- 应用菜单入口：`~/.local/share/applications/voice-note.desktop`

## 测试

```bash
cd kde
QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m unittest discover -v
```

测试默认使用明确标记的合成 PCM 验证音量计算和编码，不打开真实麦克风。
加入 `VOICE_NOTE_REAL_TEST=1` 启用短暂的真实麦克风测试（测试音频自动删除）。
实际桌面通知、托盘和文件管理器粘贴需在图形会话中另行验证。
