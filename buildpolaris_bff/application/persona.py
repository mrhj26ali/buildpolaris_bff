# FR-1.4 — role → persona resolution (priority order: highest privilege wins)
ROLE_PERSONA_PRIORITY = [
	("BuildPolaris Admin", "admin"),
	("BuildPolaris Owner", "owner"),
	("BuildPolaris Project Manager", "pm"),
	("BuildPolaris Accounting", "pm"),
	("BuildPolaris Document Controller", "pm"),
	("BuildPolaris Site Superintendent", "site_super"),
	("BuildPolaris Safety Officer", "site_super"),
	("BuildPolaris Subcontractor", "subcontractor"),
]


def resolve_persona(roles: list[str]) -> str:
	for role, persona in ROLE_PERSONA_PRIORITY:
		if role in roles:
			return persona
	return "guest"
