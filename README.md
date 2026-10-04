# 淘宝问大家采集工具

自动搜索淘宝关键词，采集每个商品的"问大家"问题和回答，导出 Excel。

## 功能

- 搜索关键词，自动获取商品列表
- 逐个商品采集"问大家"问题和回答
- 自动导出 Excel（含商品链接、问题、回答）
- 改关键词.txt 即可换关键词采集

## 快速开始

### Windows 一键运行

1. 下载 zip 解压
2. 双击 `一键采集.bat`
3. 扫码登录淘宝
4. 等它跑完，结果在 `导出结果` 文件夹

### 手动运行

```bash
pip install playwright openpyxl
playwright install chromium
python taobao_ask_crawler.py
```

## 配置

编辑 `关键词.txt`，每行一个或逗号分隔：

```
皮革,人造革,PU革,皮料
```

在 `taobao_ask_crawler.py` 顶部可调整：
- `MAX_PRODUCTS`：每个关键词采多少个商品（默认30）
- `MAX_QUESTIONS_PER_PRODUCT`：每个商品采多少个问题（默认30）

## 导出结果

Excel 包含：关键词、商品ID、商品标题、商品链接、问题、回答、回答序号、采集时间

## 免责声明

仅供学习研究使用，请遵守淘宝平台规则，控制采集频率。
