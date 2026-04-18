from app.core.workshop_templates import get_workshop_template


def test_mobile_roles_should_keep_shift_leader_editable_fields() -> None:
    shift_leader_template = get_workshop_template("cold_roll", user_role="shift_leader")
    expected_entry_names = [field["name"] for field in shift_leader_template["entry_fields"]]
    expected_extra_names = [field["name"] for field in shift_leader_template["extra_fields"]]
    expected_qc_names = [field["name"] for field in shift_leader_template["qc_fields"]]

    for role in ("team_leader", "deputy_leader", "mobile_user"):
        role_template = get_workshop_template("cold_roll", user_role=role)
        assert [field["name"] for field in role_template["entry_fields"]] == expected_entry_names
        assert [field["name"] for field in role_template["extra_fields"]] == expected_extra_names
        assert [field["name"] for field in role_template["qc_fields"]] == expected_qc_names
