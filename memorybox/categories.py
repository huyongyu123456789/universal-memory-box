from __future__ import annotations

CATEGORY_LABELS = {
    "research": "科研 / Research",
    "manuscript": "论文 / Manuscript",
    "coding": "编程 / Coding",
    "data-analysis": "数据分析 / Data Analysis",
    "teaching": "教学 / Teaching",
    "project": "项目 / Project",
    "travel": "旅行 / Travel",
    "personal": "个人 / Personal",
    "general": "其他 / General",
}

CATEGORY_KEYWORDS = {
    "manuscript": ["manuscript","paper","journal","submission","reviewer","revision","abstract","reference","citation","论文","稿件","投稿","期刊","审稿","参考文献","摘要"],
    "coding": ["code","coding","python","javascript","typescript","react","github","repository","commit","pull request","bug","debug","cli","api","mcp","agent","skill","编程","代码","脚本","仓库","调试","接口","程序","智能体"],
    "data-analysis": ["analysis","dataset","regression","model","statistics","csv","excel","table","plot","shap","training","validation","数据分析","数据集","回归","统计","模型","训练","验证","表格","图表"],
    "teaching": ["teaching","teacher","student","course","syllabus","curriculum","lesson","classroom","education","教学","教师","学生","课程","教学大纲","课堂","教育"],
    "travel": ["travel","trip","flight","hotel","restaurant","itinerary","train","tour","旅行","旅游","行程","机票","酒店","餐厅","高铁","火车","景点"],
    "research": ["research","experiment","laboratory","assay","genome","genomic","amr","antimicrobial","bacteria","microbiology","biofilm","mic","pcr","crab","科研","研究","实验","基因组","耐药","抗菌","细菌","生物膜"],
    "project": ["project","milestone","stage","batch","roadmap","workflow","task","checkpoint","项目","阶段","批次","里程碑","流程","任务","计划"],
    "personal": ["personal","family","resume","cv","application","profile","个人","家庭","简历","申请","自我介绍"],
}

PRIORITY = ["manuscript","coding","teaching","data-analysis","travel","research","project","personal"]


def normalize_category(value: str | None) -> str:
    if not value or value == "auto":
        return "general"
    v = value.strip().lower()
    aliases = {
        "科研":"research","research":"research",
        "论文":"manuscript","paper":"manuscript","manuscript":"manuscript",
        "编程":"coding","code":"coding","coding":"coding",
        "数据分析":"data-analysis","analysis":"data-analysis","data":"data-analysis",
        "教学":"teaching","teaching":"teaching",
        "项目":"project","project":"project",
        "旅行":"travel","travel":"travel",
        "个人":"personal","personal":"personal",
        "其他":"general","general":"general",
    }
    if v in CATEGORY_LABELS:
        return v
    return aliases.get(v, "general")


def infer_category(text: str) -> str:
    hay = (text or "").lower()
    scored = []
    for cat, words in CATEGORY_KEYWORDS.items():
        score = sum(hay.count(w.lower()) for w in words)
        if score:
            scored.append((score, -PRIORITY.index(cat), cat))
    if not scored:
        return "general"
    scored.sort(reverse=True)
    return scored[0][2]
