# Agent Inventory and Safety Controls

The platform includes an agent inventory foundation.

## Tracked fields

- agent id
- version
- model
- tools
- permissions
- environment
- owner
- status
- heartbeat
- last action
- current execution
- resource usage

## Implemented controls

- register agent
- heartbeat
- enable / disable
- revoke tool
- revoke permission
- global kill switch
- assert agent enabled before privileged operation

The kill switch disables all registered agents and blocks re-enable while active.
