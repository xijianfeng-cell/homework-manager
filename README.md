# 班级作业管理系统

基于 Streamlit 与 Supabase PostgreSQL 的班级作业发布、提交、催交与导出工具。

## 首次配置 Supabase

1. 在 Supabase 创建项目，等待数据库状态变为可用。
2. 进入 **SQL Editor**，新建查询，复制并运行 [supabase_schema.sql](supabase_schema.sql) 的全部内容。
3. 进入 **Project Settings → API Keys**，复制项目 URL，以及仅供服务端使用的 `service_role` / `secret` key。
4. 本地运行时，将 `.streamlit/secrets.toml.example` 复制为 `.streamlit/secrets.toml`，填入真实值；该真实文件已经被 Git 忽略。
5. Streamlit Community Cloud 部署时，在应用的 **Settings → Secrets** 粘贴：

```toml
SUPABASE_URL = "https://你的项目引用.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "你的服务端密钥"
```

`SUPABASE_SERVICE_ROLE_KEY` 权限很高，绝不能放进 `app.py`、GitHub 或发给任何学生。它只保存在 Streamlit 的服务器端 Secrets 中。

## 本地启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

数据库表建立后，首次打开应用会自动创建管理员：账号 `admin`，初始密码 `admin123`。请立即修改密码。

## 已迁移的内容

用户、作业、提交记录和通知全部存到 Supabase PostgreSQL，因此 Streamlit Community Cloud 重启不会丢失这些数据。

## 作业附件

附件会上传到 Supabase Storage 的私有 `homework-files` 桶；建表脚本会自动创建该桶，单个文件上限为 50 MB。提交记录仅保存 Storage 路径。Streamlit Cloud 重启不会影响已上传附件；删除作业或学生时，关联的云端附件也会同步删除。
