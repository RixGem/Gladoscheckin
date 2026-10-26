# Glados自动签到

### 添加**secret**

1. 跳转至自己的仓库的`Settings`->`Secrets and variables`->`Action`

2. 添加1个`repository secret`，命名为`GLADOS_COOKIES`，其值对应GLaDOS账号的cookie值中的有效部分（获取方式如下）

- 在GLaDOS的签到页面按`F12`

- 切换到`Network`页面下，刷新


- 点击第一个选项卡后在`Request Headers`下找到`Cookie`，右键复制cookie的值即可

  > 参考格式：koa:sess=eyJ1c2xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxAwMH0=; koa:sess.sig=xJkOxxxxxxxxxxxxxxxtnM;


- 多账号请在 `GLADOS_COOKIES` 中 添加多个 `cookies` 中间使用 `&`连接即可。（例如： `c1&c3&c3...`）

3. 配置积分兑换策略（非必须）

- 添加1个`repository secret`，命名为`GLADOS_EXCHANGE_PLAN`，配置自动兑换积分策略：

| 值 | 积分要求 | 兑换天数 |
|---|---------|---------|
| `plan100` | 100 积分 | 10 天 |
| `plan200` | 200 积分 | 30 天 |
| `plan500` | 500 积分 | 100 天 (默认) |

> 不配置时默认为 `plan500`，即积分达到 500 时自动兑换 100 天

4. 手机推送（非必须）

- 添加1个`repository secret`，命名为`PUSHDEER_SENDKEY`，其值对应 PushDeer key: ([获取地址](https://www.pushdeer.com/product.html))。

5. 签到域名（非必须）

- 添加1个`repository secret`（或 `Variables` 下的 `repository variable`），命名为`GLADOS_DOMAINS`，指定要签到的站点域名，多个域名用英文逗号分隔：

| 示例值 | 效果 |
|---|---|
| 不配置 | 依次签到 `glados.cloud` 与 `railgun.info`（默认） |
| `glados.cloud` | 只签到 glados.cloud（Cookie 需含 `gld:sess`/`gld:sess.sig`） |
| `railgun.info` | 只签到 railgun.info（Cookie 需含 `koa:sess`/`koa:sess.sig`） |
| `glados.cloud,railgun.info` | 两个都签到 |

> 可直接粘贴网址（如 `https://glados.cloud/console/checkin`），脚本会自动提取域名；内置列表之外的域名默认会被忽略（防止 Cookie 被发往非 GLaDOS 主机）；确认是可信的 GLaDOS 镜像时，再添加 `GLADOS_ALLOW_CUSTOM_DOMAINS=true`（secret 或 variable）启用（使用相同 API 路径，不做 Cookie 字段校验）。
> 只在一个站点有账号时建议只填该站点，避免对另一个站点发出注定失败的请求。

6. User-Agent（非必须）

- 签到返回 code 4「Automated check-in detected」时，添加`GLADOS_USER_AGENT`（secret 或 variable），值为**登录时所用浏览器**控制台中 `navigator.userAgent` 的输出。

7. 失败告警 Poke（推荐）

- 添加1个`repository secret`，命名为`POKE_API_KEY`，值为 Poke API Key。
- 签到失败（脚本退出码非 0，即任一账号在所有域名上都未签到成功、未配置 Cookie 或脚本异常）时，工作流的 `Alert via Poke` 步骤会发送一条包含本次运行链接的消息。
- 未配置 `POKE_API_KEY` 时该步骤会报错提示缺少 secret（签到本身已失败，不影响其他逻辑）。

### **star**自己的仓库


## 文件结构

```shell
│  checkin.py	# 签到脚本
│  logging_config.py	# 日志配置
│
├─tests
│      test_checkin.py	# 单元测试 (python -m unittest discover -s tests)
│
├─.github
│  └─workflows
│          gladosCheck.yml	# Actions 配置文件
```


## 声明

本项目不保证稳定运行与更新, 因GitHub相关规定可能会删库, 请注意备份







