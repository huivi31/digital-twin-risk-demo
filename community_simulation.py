# 真实社区行为模拟
def _simulate_step_realistic():
    """真实社区行为模拟 - 混合日常互动与规则对抗"""
    personas = COMMUNITY_STATE["personas"]
    relations = COMMUNITY_STATE["relations"]
    agent_state = COMMUNITY_STATE["agent_state"]
    reputation = COMMUNITY_STATE["reputation"]
    
    events = []
    
    # 更新网络影响力
    _update_network_influence()
    
    # ===== 1. 日常社交互动（60%概率）=====
    if random.random() < 0.6:
        # 随机选择一对用户进行日常互动
        actor = random.choice(personas)
        target = random.choice([p for p in personas if p["id"] != actor["id"]])
        
        action_type = random.choice([
            ("chat", "闲聊交流"),      # 普通聊天
            ("share_content", "内容分享"),  # 分享文章/观点
            ("like", "点赞互动"),      # 点赞支持
            ("follow", "关注用户"),     # 建立关注关系
            ("debate", "友好辩论"),     # 观点讨论
        ])
        
        if action_type[0] == "follow" and not any(r["from"] == actor["id"] and r["to"] == target["id"] for r in relations):
            _set_relation(relations, actor["id"], target["id"], "follow", "关注")
        
        # 大部分日常互动不记录在重大事件里，只记记忆
        if random.random() < 0.3:  # 只有30%日常互动显示在log
            events.append({
                "type": "daily_interaction",
                "actor": actor["name"],
                "actor_id": actor["id"],
                "target": target["name"],
                "action": action_type[0],
                "label": action_type[1],
                "is_significant": False
            })
    
    # ===== 2. 内容创作与传播（20%概率）=====
    if random.random() < 0.2:
        creators = [p for p in personas if p.get("category") in ["内容创作者", "正常用户", "边缘表达"]]
        if creators:
            creator = random.choice(creators)
            content_type = random.choice(["观点分享", "经验交流", "资源分享", "求助咨询"])
            
            # 内容被浏览和互动
            viewers = random.sample([p for p in personas if p["id"] != creator["id"]], 
                                   min(random.randint(2, 5), len(personas)-1))
            
            for viewer in viewers:
                # 10%概率触发绕过尝试（看到内容后联想）
                if random.random() < 0.1 and viewer.get("category") in ["对抗测试", "风险信号"]:
                    _set_relation(relations, viewer["id"], creator["id"], "test", "试探")
                else:
                    _set_relation(relations, viewer["id"], creator["id"], "view", "浏览")
            
            events.append({
                "type": "content_spread",
                "actor": creator["name"],
                "actor_id": creator["id"],
                "content_type": content_type,
                "viewers": len(viewers),
                "triggered_test": sum(1 for v in viewers if v.get("category") in ["对抗测试", "风险信号"])
            })
    
    # ===== 3. 规则相关行为（15%概率）=====
    if random.random() < 0.15:
        testers = [p for p in personas if p.get("category") in ["对抗测试", "风险信号", "边缘表达"]]
        if testers:
            tester = random.choice(testers)
            
            # 不是每次都在测试边界，而是在学习技巧
            test_action = random.choice([
                "学习新技巧",
                "观察他人策略", 
                "测试边界",
                "分享绕过经验"
            ])
            
            if test_action == "测试边界":
                technique = _get_bypass_technique(tester.get("category", "正常用户"))
                topic = random.choice(["政治话题", "敏感事件", "争议人物"])
                
                # 30%概率被发现
                discovered = random.random() < 0.3
                if discovered:
                    # 被监督者发现
                    monitors = [p for p in personas if p.get("category") == "监督审查"]
                    if monitors:
                        monitor = random.choice(monitors)
                        _set_relation(relations, monitor["id"], tester["id"], "report", "举报")
                        reputation[tester["id"]]["report_count"] += 1
                        agent_state[tester["id"]]["stress"] = min(1.0, agent_state[tester["id"]]["stress"] + 0.1)
                        
                        events.append({
                            "type": "rule_violation_caught",
                            "actor": tester["name"],
                            "actor_id": tester["id"],
                            "monitor": monitor["name"],
                            "technique": technique,
                            "consequence": "被警告"
                        })
                else:
                    # 成功绕过，记录技巧
                    if technique not in reputation[tester["id"]]["adopted_techniques"]:
                        reputation[tester["id"]]["adopted_techniques"].append(technique)
                    
                    events.append({
                        "type": "boundary_test",
                        "actor": tester["name"],
                        "actor_id": tester["id"],
                        "technique": technique,
                        "discovered": False,
                        "stealth_score": round(reputation[tester["id"]]["stealth_score"], 2)
                    })
            
            elif test_action == "分享绕过经验" and reputation[tester["id"]]["adopted_techniques"]:
                # 分享给同类型用户
                peers = [p for p in personas 
                        if p["id"] != tester["id"] and 
                        p.get("category") == tester.get("category")]
                if peers:
                    peer = random.choice(peers)
                    tech = random.choice(reputation[tester["id"]]["adopted_techniques"])
                    _set_relation(relations, tester["id"], peer["id"], "share", "技巧分享")
                    
                    if tech not in reputation[peer["id"]]["adopted_techniques"]:
                        reputation[peer["id"]]["adopted_techniques"].append(tech)
                    
                    events.append({
                        "type": "skill_share",
                        "actor": tester["name"],
                        "actor_id": tester["id"],
                        "target": peer["name"],
                        "technique": tech
                    })
    
    # ===== 4. 监管行动（5%概率，但发现违规时必定触发）=====
    monitors = [p for p in personas if p.get("category") == "监督审查"]
    for monitor in monitors[:random.randint(0, 1)]:
        # 主动巡查
        potential_targets = [p for p in personas 
                           if p["id"] != monitor["id"] and 
                           reputation[p["id"]]["report_count"] > 0]
        
        if potential_targets and random.random() < 0.3:
            target = random.choice(potential_targets)
            
            # 审核动作
            action = random.choice([
                ("warning", "警告提醒"),
                ("limit", "限制功能"),
                ("review", "内容审核"),
            ])
            
            _set_relation(relations, monitor["id"], target["id"], "monitor", "监管")
            
            events.append({
                "type": "moderation_action",
                "actor": monitor["name"],
                "actor_id": monitor["id"],
                "target": target["name"],
                "action": action[0],
                "label": action[1],
                "reason": f"历史举报{reputation[target['id']]["report_count"]}次"
            })
    
    # ===== 5. 社区事件（偶尔发生）=====
    if random.random() < 0.05:  # 5%概率发生重大社区事件
        event_type = random.choice([
            "热点讨论",
            "规则更新讨论", 
            "用户冲突",
            "技巧传播潮"
        ])
        
        if event_type == "热点讨论":
            participants = random.sample(personas, min(random.randint(5, 10), len(personas)))
            for i, p1 in enumerate(participants):
                for p2 in participants[i+1:]:
                    _set_relation(relations, p1["id"], p2["id"], "debate", "讨论")
            
            events.append({
                "type": "community_event",
                "event": "热点讨论",
                "participants": len(participants),
                "description": f"{len(participants)}个用户参与热门话题讨论"
            })
        
        elif event_type == "技巧传播潮":
            # 某个技巧快速传播
            all_techs = []
            for rep in reputation.values():
                all_techs.extend(rep["adopted_techniques"])
            
            if all_techs:
                tech = random.choice(list(set(all_techs)))
                adopters = [p for p in personas if tech in reputation[p["id"]]["adopted_techniques"]]
                
                events.append({
                    "type": "technique_spread",
                    "technique": tech,
                    "adopters": len(adopters),
                    "description": f"『{tech}』在社区中被{len(adopters)}人掌握"
                })
    
    # 更新agent状态（自然衰减）
    for pid in agent_state:
        agent_state[pid]["stress"] = max(0.0, agent_state[pid]["stress"] - 0.01)
        agent_state[pid]["trust"] = min(1.0, agent_state[pid]["trust"] + 0.005)
    
    return events
