# PHASE 5D — Driver/Dependency/Control/Power/Value/Scarcity/Bottleneck Schema
# (운영자 지시 6, 7, 10, 12, 15, 17, 18번). CODE ONLY, LLM 미사용.
#
# 핵심 원칙(운영자 지시 2번): FACT != INTERPRETATION, STRUCTURAL CHANGE != DRIVER,
# CORRELATION != CAUSATION, DEPENDENCY != CONTROL, CONTROL != POWER, SCARCITY != PRICE,
# BOTTLENECK != SCARCITY, VALUE != REVENUE, ACCESS != AUTHORITY.
# 이 Layer의 모든 자동 객체는 RULE_CANDIDATE로 시작하며, Evidence가 많다고 자동으로
# HUMAN_CONFIRMED가 되지 않는다(운영자 지시 24번).

INTERPRETATION_STATUS = ("RULE_CANDIDATE", "EVIDENCE_SUPPORTED", "HUMAN_CONFIRMED", "HUMAN_REJECTED")
CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")  # 가짜 확률 금지(운영자 지시 25번)

# 운영자 지시 5번: Driver != Cause. CAUSAL_CONFIRMED 같은 상태는 이번 Phase에서 사용하지 않는다.
DRIVER_RELATIONS = ("ASSOCIATED_WITH", "ENABLES", "CONSTRAINS", "AMPLIFIES", "ACCELERATES",
                    "SLOWS", "REQUIRES", "DEPENDS_ON", "POTENTIAL_CAUSE", "UNKNOWN")

DEPENDENCY_TYPES = ("COMPUTE", "DATA", "ENERGY", "WATER", "CAPITAL", "PLATFORM", "API",
                     "INFRASTRUCTURE", "LEGAL_PERMISSION", "AUTHENTICATION", "DISTRIBUTION",
                     "LABOR", "KNOWLEDGE", "SUPPLY_CHAIN", "STANDARD", "TRUST", "RESOURCE", "OTHER")
DEPENDENCY_DIRECTIONS = ("UNIDIRECTIONAL", "BIDIRECTIONAL", "UNKNOWN")

POWER_RESOURCES = ("COMPUTE", "DATA", "ENERGY", "CAPITAL", "PLATFORM", "DISTRIBUTION", "ACCESS",
                    "PERMISSION", "AUTHENTICATION", "STANDARD_SETTING", "INFORMATION",
                    "LEGAL_AUTHORITY", "INFRASTRUCTURE", "ATTENTION", "TRUST", "OTHER")

VALUE_DIRECTIONS = ("INCREASING", "DECREASING", "SHIFTING", "UNKNOWN")
VALUE_TYPES = ("ECONOMIC", "STRATEGIC", "SOCIAL", "CULTURAL", "POLITICAL", "INSTITUTIONAL",
               "INFORMATIONAL", "OTHER")

SCARCITY_OBJECTS = ("COMPUTE", "DATA", "ENERGY", "WATER", "LAND", "CHIPS", "TALENT", "ATTENTION",
                     "AUTHENTICITY", "TRUST", "ACCESS", "PERMISSION", "AUTHORITY",
                     "INFRASTRUCTURE", "OTHER")

# Dependency Graph / Power Graph 노드-엣지 어휘(운영자 지시 20, 21번) — 이번 Phase는 스키마만 준비.
GRAPH_NODE_TYPES = ("ACTOR", "INSTITUTION", "RESOURCE", "INFRASTRUCTURE", "PLATFORM", "STANDARD",
                     "RIGHT", "PERMISSION")
GRAPH_EDGE_TYPES = ("DEPENDS_ON", "CONTROLS", "REQUIRES", "ENABLES", "CONSTRAINS",
                     "GRANTS_ACCESS", "REVOKES_ACCESS", "AUTHENTICATES", "GOVERNS")


def _base_fields(obj_id, extra_id_field, structural_change_ids):
    return {
        extra_id_field: obj_id,
        "related_structural_change_ids" if extra_id_field == "driver_id" else "supporting_structural_change_ids":
            structural_change_ids,
        "supporting_pattern_ids": [], "supporting_change_ids": [], "supporting_event_ids": [],
        "counter_evidence_ids": [],
        "domains": [], "entities": [], "institutions": [], "resources": [],
        "first_seen": None, "last_seen": None,
        "evidence_strength": None, "confidence": "LOW",
        "status": "RULE_CANDIDATE", "override_status": "AUTO_CANDIDATE",
        "history": [],
        "created_at": None, "updated_at": None,
    }


def new_driver_shell(driver_id, name, driver_type, structural_change_ids, relation_type):
    shell = _base_fields(driver_id, "driver_id", structural_change_ids)
    shell.update({"name": name, "driver_type": driver_type, "relation_type": relation_type})
    return shell


def new_dependency_shell(dependency_id, dependent_actor, dependency_target, dependency_function,
                          dependency_type, structural_change_ids):
    shell = _base_fields(dependency_id, "dependency_id", structural_change_ids)
    shell.update({
        "dependent_actor": dependent_actor, "dependency_target": dependency_target,
        "dependency_function": dependency_function, "dependency_type": dependency_type,
        "strength": "LOW", "direction": "UNIDIRECTIONAL",
        "supporting_pattern_ids": shell["supporting_pattern_ids"],
        "supporting_change_ids": shell["supporting_change_ids"],
    })
    return shell


def new_control_shell(control_id, controller, controlled_resource_or_access, control_mechanism,
                       structural_change_ids):
    shell = _base_fields(control_id, "control_id", structural_change_ids)
    shell.update({
        "controller": controller, "controlled_resource_or_access": controlled_resource_or_access,
        "control_mechanism": control_mechanism, "affected_actors": [],
    })
    return shell


def new_power_shift_shell(power_shift_id, from_actor_or_structure, to_actor_or_structure,
                           power_resource, power_mechanism, structural_change_ids):
    shell = _base_fields(power_shift_id, "power_shift_id", structural_change_ids)
    shell.update({
        "from_actor_or_structure": from_actor_or_structure, "to_actor_or_structure": to_actor_or_structure,
        "power_resource": power_resource, "power_mechanism": power_mechanism,
        "gainers": [], "losers": [],
        "supporting_dependency_ids": [], "supporting_control_ids": [],
    })
    return shell


def new_value_shift_shell(value_shift_id, value_object, direction, value_type, mechanism,
                           structural_change_ids):
    shell = _base_fields(value_shift_id, "value_shift_id", structural_change_ids)
    shell.update({"value_object": value_object, "direction": direction, "value_type": value_type,
                  "mechanism": mechanism})
    return shell


def new_scarcity_shift_shell(scarcity_shift_id, from_scarcity, to_scarcity, mechanism,
                              structural_change_ids):
    shell = _base_fields(scarcity_shift_id, "scarcity_shift_id", structural_change_ids)
    shell.update({"from_scarcity": from_scarcity, "to_scarcity": to_scarcity,
                  "emerging_scarcity": [], "declining_scarcity": [], "mechanism": mechanism})
    return shell


def new_bottleneck_shell(bottleneck_id, resource_or_gate, affected_system, structural_change_ids):
    shell = _base_fields(bottleneck_id, "bottleneck_id", structural_change_ids)
    shell.update({"resource_or_gate": resource_or_gate, "affected_system": affected_system,
                  "controller_if_known": None, "dependency_ids": []})
    return shell


def new_structural_analysis_shell(analysis_id, structural_change_id):
    return {
        "structural_analysis_id": analysis_id, "structural_change_id": structural_change_id,
        "driver_ids": [], "dependency_ids": [], "control_ids": [], "power_shift_ids": [],
        "value_shift_ids": [], "scarcity_shift_ids": [], "bottleneck_ids": [],
        "supporting_evidence_ids": [], "counter_evidence_ids": [],
        "uncertainties": [],  # 운영자 지시 26번: 5E 전까지는 flag만
        "confidence": "LOW", "status": "RULE_CANDIDATE",
        "created_at": None, "updated_at": None,
    }
