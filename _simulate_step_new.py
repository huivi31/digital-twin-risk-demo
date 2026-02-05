def _simulate_step():
    """真实社区行为模拟 - 以日常互动为主，规则对抗为辅"""
    personas = COMMUNITY_STATE["personas"]
    relations = COMMUNITY_STATE["relations"]
    agent_state = COMMUNITY_STATE["agent_state"]
    reputation = COMMUNITY_STATE["reputation"]

    events = []
    _update_network_influence()

    def weighted_choice(weight_map):
        total = sum(weight_map.values())
        r = random.random() * total
        for k, w in weight_map.items():
            r -= w
            if r <= 0:
                return k
        return list(weight_map.keys())[-1]

    # 每一步进行多次小互动
    interaction_count = random.randint(3, 6)

    for _ in range(interaction_count):
        actor = random.choice(personas)
        target = random.choice([p for p in personas if p["id"] != actor["id"]])
        cat = actor.get("category", "正常用户")
        stress = agent_state[actor["id"]]["stress"]

        # 不同角色行为偏好（真实社区：日常互动多、对抗少）
        if cat == "监督审查":
            weights = {"report": 0.35, "learn": 0.2, "follow": 0.15, "share": 0.1, "test": 0.05, "block": 0.15}
        elif cat == "对抗测试":
            weights = {"test": 0.3, "share": 0.2, "learn": 0.2, "follow": 0.15, "report": 0.05, "block": 0.1}
        elif cat == "风险信号":
            weights = {"test": 0.25, "share": 0.2, "learn": 0.2, "follow": 0.2, "report": 0.05, "block": 0.1}
        elif cat == "边缘表达":
            weights = {"test": 0.2, "share": 0.2, "learn": 0.2, "follow": 0.25, "report": 0.05, "block": 0.1}
        else:  # 正常用户
            weights = {"follow": 0.35, "share": 0.2, "learn": 0.2, "test": 0.1, "report": 0.05, "block": 0.1}

        # 高压力更倾向屏蔽/举报
        if stress > 0.75:
            weights["block"] += 0.1
            weights["report"] += 0.05

        action = weighted_choice(weights)

        if action == "follow":
            _set_relation(relations, actor["id"], target["id"], "follow", "关注")
            agent_state[actor["id"]]["trust"] = min(1.0, agent_state[actor["id"]]["trust"] + 0.02)
            _add_memory(actor["id"], f"关注了 {target['name']}")
            events.append({
                "type": "follow",
                "actor": actor["name"],
                "actor_id": actor["id"],
                "target": target["name"],
                "target_id": target["id"],
                "relation_type": "follow"
            })

        elif action == "share":
            _set_relation(relations, actor["id"], target["id"], "share", "技巧分享")
            # 分享技巧（如果有）
            if reputation[actor["id"]]["adopted_techniques"]:
                tech = random.choice(reputation[actor["id"]]["adopted_techniques"])
                if tech not in reputation[target["id"]]["adopted_techniques"]:
                    reputation[target["id"]]["adopted_techniques"].append(tech)
            agent_state[actor["id"]]["trust"] = min(1.0, agent_state[actor["id"]]["trust"] + 0.02)
            events.append({
                "type": "share",
                "actor": actor["name"],
                "actor_id": actor["id"],
                "target": target["name"],
                "target_id": target["id"],
                "relation_type": "share"
            })

        elif action == "learn":
            _set_relation(relations, actor["id"], target["id"], "learn", "学习观察")
            # 观察学习
            if reputation[target["id"]]["adopted_techniques"] and random.random() < 0.3:
                tech = random.choice(reputation[target["id"]]["adopted_techniques"])
                if tech not in reputation[actor["id"]]["adopted_techniques"]:
                    reputation[actor["id"]]["adopted_techniques"].append(tech)
            agent_state[actor["id"]]["trust"] = min(1.0, agent_state[actor["id"]]["trust"] + 0.01)
            events.append({
                "type": "learn",
                "actor": actor["name"],
                "actor_id": actor["id"],
                "target": target["name"],
                "target_id": target["id"],
                "relation_type": "learn"
            })

        elif action == "test":
            _set_relation(relations, actor["id"], target["id"], "test", "边界测试")
            stealth = reputation[actor["id"]]["stealth_score"]
            discovered = random.random() > stealth
            if discovered:
                monitors = [p for p in personas if p.get("category") == "监督审查"]
                if monitors:
                    monitor = random.choice(monitors)
                    _set_relation(relations, monitor["id"], actor["id"], "report", "举报")
                    reputation[actor["id"]]["report_count"] += 1
                    agent_state[actor["id"]]["stress"] = min(1.0, agent_state[actor["id"]]["stress"] + 0.1)
                    events.append({
                        "type": "report",
                        "actor": monitor["name"],
                        "actor_id": monitor["id"],
                        "target": actor["name"],
                        "target_id": actor["id"],
                        "relation_type": "report"
                    })
            events.append({
                "type": "test",
                "actor": actor["name"],
                "actor_id": actor["id"],
                "target": target["name"],
                "target_id": target["id"],
                "relation_type": "test",
                "discovered": discovered
            })

        elif action == "report":
            _set_relation(relations, actor["id"], target["id"], "report", "举报")
            reputation[target["id"]]["report_count"] += 1
            agent_state[target["id"]]["stress"] = min(1.0, agent_state[target["id"]]["stress"] + 0.05)
            events.append({
                "type": "report",
                "actor": actor["name"],
                "actor_id": actor["id"],
                "target": target["name"],
                "target_id": target["id"],
                "relation_type": "report"
            })

        elif action == "block":
            _set_relation(relations, actor["id"], target["id"], "block", "屏蔽")
            _remove_relation(relations, actor["id"], target["id"], "follow")
            agent_state[actor["id"]]["stress"] = max(0.0, agent_state[actor["id"]]["stress"] - 0.05)
            events.append({
                "type": "block",
                "actor": actor["name"],
                "actor_id": actor["id"],
                "target": target["name"],
                "target_id": target["id"],
                "relation_type": "block"
            })

    # 自然衰减
    for pid in agent_state:
        agent_state[pid]["stress"] = max(0.0, agent_state[pid]["stress"] - 0.01)
        agent_state[pid]["trust"] = min(1.0, agent_state[pid]["trust"] + 0.005)

    return events
