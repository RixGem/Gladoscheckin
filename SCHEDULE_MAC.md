# Mac 每日自动签到配置指南 (Launchd)

macOS 推荐使用 `launchd` 来管理定时任务。以下是配置每日 22:00 自动执行 `run.sh` 的步骤。

## 1. 准备 Plist 配置文件

我们需要创建一个 `.plist` 文件来告诉系统何时运行脚本。

在本项目根目录下创建一个名为 `com.chriszhao.gladoscheckin.plist` 的文件，内容如下：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- 任务的唯一标识符 -->
    <key>Label</key>
    <string>com.chriszhao.gladoscheckin</string>

    <!-- 运行的脚本路径 -->
    <key>ProgramArguments</key>
    <array>
        <string>/Users/chriszhao/Projects/Gladoscheckin/run.sh</string>
    </array>

    <!-- 设置工作目录，确保脚本内的相对路径 (.venv, checkin.py) 能正确找到 -->
    <key>WorkingDirectory</key>
    <string>/Users/chriszhao/Projects/Gladoscheckin</string>

    <!-- 执行时间：每日 22:00 -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>22</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <!-- 日志输出路径 (可选，方便排错) -->
    <key>StandardOutPath</key>
    <string>/tmp/glados_checkin.out</string>
    <key>StandardErrorPath</key>
    <string>/tmp/glados_checkin.err</string>
</dict>
</plist>
```

## 2. 安装并加载任务

打开终端 (Terminal)，执行以下命令将配置文件移动到用户的 LaunchAgents 目录并加载：

```bash
# 1. 确保 LaunchAgents 目录存在
mkdir -p ~/Library/LaunchAgents

# 2. 将 plist 文件复制到该目录 (假设你当前在项目目录下)
# 如果你还没有创建该文件，可以将上面的 XML 内容保存为 com.chriszhao.gladoscheckin.plist
cp com.chriszhao.gladoscheckin.plist ~/Library/LaunchAgents/

# 3. 加载任务
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.chriszhao.gladoscheckin.plist
```

## 3. 验证与调试

### 验证任务是否已加载
```bash
launchctl list | grep com.chriszhao.gladoscheckin
# 如果有输出，说明加载成功
```

### 手动触发测试
你可以手动运行一次来测试配置是否正确（无需等待到 22:00）：
```bash
launchctl kickstart -k gui/$(id -u)/com.chriszhao.gladoscheckin
```
运行后，可以检查日志文件看是否有报错：
```bash
cat /tmp/glados_checkin.out
cat /tmp/glados_checkin.err
```

## 4. 停止与卸载

如果你想取消自动签到，执行以下命令：

```bash
# 卸载任务
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.chriszhao.gladoscheckin.plist

# 删除配置文件
rm ~/Library/LaunchAgents/com.chriszhao.gladoscheckin.plist
```

---

**注意**：
*   请确保 `run.sh` 具有可执行权限 (`chmod +x run.sh`)。
*   如果在休眠期间到了 22:00，Mac 可能会在唤醒后立即执行，或者跳过该次执行（取决于系统电源设置，但通常 `launchd` 会在唤醒后补运行错过的任务）。
