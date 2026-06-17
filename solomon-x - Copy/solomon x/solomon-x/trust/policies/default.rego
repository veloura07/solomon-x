package solomon.authz

# Default deny all permissions
default allow = false
default requires_mentor_gate = false

# Rule 1: Allow if agent has wildcard scope and meets trust/confidence requirements
allow {
    input.allowed_scopes[_] == "*"
    input.trust_level >= input.min_trust
    input.confidence >= input.min_confidence
}

# Rule 2: Allow if agent has specific scope and meets trust/confidence requirements
allow {
    input.allowed_scopes[_] == input.action
    input.trust_level >= input.min_trust
    input.confidence >= input.min_confidence
}

# Rule 3: Trigger mentor gate if action is allowed but confidence is below safety approval threshold
requires_mentor_gate {
    allow
    input.confidence < input.requires_approval_below
}
