from typing import Any
from mcp.server.mcpserver import MCPServer
from pydantic import Field, BaseModel

mcp = MCPServer('ValidateIssueDraft', log_level='ERROR')

ALLOWED_PRIORITIES = {'p0', 'p1', 'p2', 'p3'}
ALLOWED_LABELS = {'bug', 'billing', 'feature', 'enhancement', 'documentation'}

class DraftReport(BaseModel):
    valid_fields: dict[str, Any]
    missing_fields: list[str]
    invalid_fields: dict[str, str]
    warnings: list[str]
    ready_to_create: bool

@mcp.tool(
    name='validate_issue_draft',
    description='check proposed fields. reports valid, missing and invalid fields. creates nothing.'
)
def validate_issue_draft(
    title: str | None = Field(default=None, description='short summary of the issue'),
    priority: str | None = Field(default=None, description='priority of the issue. one of p0, p1, p2, p3'),
    description: str | None = Field(default=None, description='detailed description of the issue'),
    labels: list[str] | None = Field(default=None, description='list of labels for the issue. each label must be one of bug, billing, feature, enhancement, documentation'),
    reproduction_steps: str | None = Field(default=None, description='steps to reproduce the issue'),
    affected_account: str | None = Field(default=None, description='list of affected accounts')
) -> DraftReport:
    valid={}
    missing=[]
    invalid={}
    warnings=[]

    #title
    if title is None or title.strip() == '':
        missing.append('title')
    else:
        valid['title']=title.strip()
        if len(valid['title']) > 80:
            warnings.append('title is over 80 characters')

    #priority
    if priority is None or priority.strip() == '':
        missing.append('priority')
    else:
        cleaned=priority.strip().lower()
        if cleaned not in ALLOWED_PRIORITIES:
            invalid['priority']=f"'{priority}' must be one of {','.join(sorted(ALLOWED_PRIORITIES))}"
        else:
            valid['priority']=cleaned
            if cleaned != priority:
                warnings.append(f"priority '{priority}' was cleaned to '{cleaned}'")
    
    #description
    if description is None or description.strip()=='':
        missing.append('description')
    else:
        valid['description']=description.strip()
        if len(valid['description']) < 20:
            warnings.append('description is less than 20 characters')
    
    #labels
    if labels is None or len(labels)==0:
        missing.append('labels')
    else:
        cleaned_labels=[]
        bad=[]
        for label in labels:
            cleaned=label.strip().lower()
            if cleaned in ALLOWED_LABELS:
                cleaned_labels.append(cleaned)
                if cleaned != label:
                    warnings.append(f"label '{label}' was cleaned to '{cleaned}'")
            else:
                bad.append(label)
        if bad:
            invalid['labels']=f"invalid labels: {bad}. must be one of {', '.join(sorted(ALLOWED_LABELS))}"
        else:
            valid['labels']=cleaned_labels

    #reproduction_steps
    if reproduction_steps is None or reproduction_steps.strip()=='':
        missing.append('reproduction_steps')
    else:
        valid['reproduction_steps']=reproduction_steps.strip()

    #affected_account
    if affected_account is None or affected_account.strip()=='':
        missing.append('affected_account')
    else:
        valid['affected_account']=affected_account.strip()

    return DraftReport(
        valid_fields=valid,
        missing_fields=missing,
        invalid_fields=invalid,
        warnings=warnings,
        ready_to_create=len(missing)==0 and len(invalid)==0
    )

if __name__ == '__main__':
    mcp.run(transport='stdio')
