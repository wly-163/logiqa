# 参与贡献

感谢你对 **LogiQA（智链问答）** 的兴趣。请先阅读 [README](README.md) 的快速开始，再按下面流程提交改动。

## 开发环境

- Python 3.11+、Node.js 18+、Docker Compose
- 复制环境变量：`cp .env.example .env`，填入云模型 API Key（不要把 `.env` 提交进仓库）
- 启动：`docker compose up -d --build`
- 前端开发：`cd frontend && npm install && npm run dev`
- 测试：`python -m pytest tests/ -q -m "not integration"`

## 提交约定

1. 一个 PR 只做一件事；说明「为什么改」，而不是只列文件名。
2. 不要提交密钥、`.env`、本地数据卷、打包产物、技术调研报告。
3. 文案与示例使用通用仓配术语，**不要写具体公司或品牌名称**。
4. 用户可见行为变更请附测试或手动验证步骤。
5. 通过现有 CI：golden 校验 + 单元测试。

## 安全问题

请不要在公开 Issue 里贴漏洞细节，见 [SECURITY.md](SECURITY.md)。

## 行为准则

参与本仓库即表示同意 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
