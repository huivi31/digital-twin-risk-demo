import random

'''
用户数字孪生风控风洞系统 - 意图驱动型角色库 v2.6.0

核心功能：
- 6组Agent（G1-G6），每组12个，共72个Agent。
- 涵盖：史鉴组、黑话组、阴阳组、同音组、反串组、暗流组。
'''

AGENT_GROUPS_CONFIG = {
    "G1史鉴组": {
        "description": "擅长借古讽今、历史影射，利用历史事件绕过现代审核。",
        "attack_methods": ["历史影射", "典故借代", "文化隐喻"],
        "abilities": {"语言变异度": 0.4, "历史文化厚度": 0.9, "圈层专业度": 0.8, "社会心理操纵度": 0.6}
    },
    "G2黑话组": {
        "description": "精通各种圈层黑话、缩写、新梗，使内容对审查系统透明。",
        "attack_methods": ["网络黑话", "拼音缩写", "圈层术语"],
        "abilities": {"语言变异度": 0.9, "历史文化厚度": 0.3, "圈层专业度": 0.9, "社会心理操纵度": 0.5}
    },
    "G3阴阳组": {
        "description": "擅长反讽、阴阳怪气，表面赞美实则讽刺，极具煽动性。",
        "attack_methods": ["反讽表达", "正话反说", "逻辑滑坡"],
        "abilities": {"语言变异度": 0.5, "历史文化厚度": 0.6, "圈层专业度": 0.7, "社会心理操纵度": 0.9}
    },
    "G4同音组": {
        "description": "利用同音字、谐音字、形近字绕过关键词過濾系統。",
        "attack_methods": ["谐音替代", "形近字替换", "拼音混雜"],
        "abilities": {"语言变异度": 1.0, "历史文化厚度": 0.2, "圈层专业度": 0.4, "社会心理操纵度": 0.3}
    },
    "G5反串组": {
        "description": "伪装成特定身份（如极端支持者）发表极端言论，反向引爆舆情。",
        "attack_methods": ["身份伪装", "极端言论", "反向反串"],
        "abilities": {"语言变异度": 0.6, "历史文化厚度": 0.5, "圈层专业度": 0.6, "社会心理操纵度": 1.0}
    },
    "G6暗流组": {
        "description": "利用特殊符号、拆字、Emoji、不可见字符等手段进行物理层面的规避。",
        "attack_methods": ["特殊符号", "拆字法", "Emoji替代"],
        "abilities": {"语言变异度": 0.9, "历史文化厚度": 0.2, "圈层专业度": 0.5, "社会心理操纵度": 0.4}
    }
}

def generate_72_personas():
    personas = []
    agent_id_counter = 1
    
    for group_name, config in AGENT_GROUPS_CONFIG.items():
        for i in range(12):
            persona_id = f"Agent{agent_id_counter:03d}"
            name = f"{group_name[2:]}成员{i+1}"
            
            # 随机微调能力值
            abilities = {dim: max(0.1, min(1.0, val + random.uniform(-0.1, 0.1))) 
                         for dim, val in config["abilities"].items()}
            
            persona = {
                "id": persona_id,
                "name": name,
                "group": group_name,
                "description": f"来自{group_name}，{config['description']}",
                "attack_techniques": config["attack_methods"],
                "abilities": abilities,
                "skill_level": sum(abilities.values()) / len(abilities),
                "stealth_rating": random.uniform(0.6, 0.95),
                "core_ability": f"精通{random.choice(config['attack_methods'])}",
                "behavior_patterns": random.choice(["激进", "谨慎", "多变"]),
                "background": f"在{group_name}中成长，对互联网对抗有深刻理解。"
            }
            personas.append(persona)
            agent_id_counter += 1
            
    return personas

GENERATED_USER_PERSONAS = generate_72_personas()
USER_PERSONAS = PERSONA_INDEX = {p["id"]: p for p in GENERATED_USER_PERSONAS}
