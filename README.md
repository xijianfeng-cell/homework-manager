# 班级作业管理系统

一个 Streamlit + SQLite 的轻量作业收集工具。管理员发布作业、添加学生、查看提交看板、生成催交名单并导出 Excel；学生登录后即可上传作业。

## 启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

首次启动会创建 `classwork.db` 与 `uploads/`。管理员初始账号为 `admin`，初始密码为 `admin123`；请登录后立刻在侧边栏修改密码。

## 使用顺序

1. 管理员登录后，在“学生管理”逐个添加学生：登录账号为其学号。
2. 在“发布作业”写明科目、要求和截止时间。
3. 将页面链接发到班群；学生登录并上传文件。
4. 在“提交看板”查看未交/迟交情况，在“催交与导出”复制催交文案或下载 Excel。

文件以“学号_时间戳_原文件名”保存到 `uploads/`，不会因同名而覆盖。数据库只存储 SHA-256 密码哈希，不保存明文密码。
