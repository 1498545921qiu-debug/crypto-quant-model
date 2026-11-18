# 部署到 Streamlit Community Cloud 的步骤

## 准备工作
1. 注册 GitHub 账号：https://github.com
2. 注册 Streamlit Cloud：https://share.streamlit.io （用 GitHub 登录即可）

## 部署步骤

### 第1步：把代码上传到 GitHub
1. 在 GitHub 新建一个仓库（Repository），设为 Public。
2. 把以下文件上传到仓库根目录：
   - `streamlit_quant_app.py`
   - `requirements.txt`
   - （可选）`README.md`

### 第2步：在 Streamlit Cloud 部署
1. 打开 https://share.streamlit.io
2. 点击右上角 **New app**
3. 选择你的 GitHub 仓库
4. 主文件路径填写：`streamlit_quant_app.py`
5. 点击 **Deploy**

### 第3步：等待部署完成
- 通常 1-3 分钟即可完成
- 部署成功后会生成一个链接，例如：
  `https://你的用户名-仓库名-streamlit-quant-app-xxxx.streamlit.app`
- 把这个链接收藏或分享即可在线使用

## 注意事项
- 仓库必须是 **Public**（公开）才能免费部署
- 每次修改代码并 push 到 GitHub 后，在线应用会自动更新
- 免费版有一定资源限制，适合个人学习和演示

## 其他部署方式（可选）
- Hugging Face Spaces（也支持 Streamlit）
- Railway / Render（需要稍微多一点配置）
