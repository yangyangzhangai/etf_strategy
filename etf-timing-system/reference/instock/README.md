# InStock 独立参考环境

该环境按 InStock 官方 Docker 方式拆分为 MariaDB 和 InStock 两个容器，只用于查看完整系统效果和参考其定时采集架构，不与 ETF 择时系统共享数据库。

1. 安装并启动 Docker Desktop。
2. 将 `.env.example` 复制为 `.env`，替换为随机数据库密码。
3. 在本目录运行 `docker compose up -d`。
4. 首次初始化完成后打开 `http://localhost:9988/`。

`proxy.txt` 和 `eastmoney_cookie.txt` 默认留空；只有确实需要时才填写。镜像来自项目官方 README 中的 `mayanghua/instock:latest`。当前电脑尚未安装 Docker，因此该参考环境已生成但未在本机启动验证。
