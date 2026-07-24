# LivePulse API

## Host

- `POST /api/events`
- `GET /api/events`
- `GET /api/events/{event_id}`
- `GET /api/events/{event_id}/state`
- `PATCH /api/events/{event_id}`
- `POST /api/events/{event_id}/questions`
- `PUT /api/questions/{question_id}`
- `DELETE /api/questions/{question_id}`
- `POST /api/events/{event_id}/questions/reorder`
- `POST /api/events/{event_id}/actions/lobby`
- `POST /api/events/{event_id}/actions/waiting`
- `POST /api/questions/{question_id}/actions/open`
- `POST /api/questions/{question_id}/actions/close`
- `POST /api/questions/{question_id}/actions/reveal`
- `POST /api/events/{event_id}/actions/end`
- `GET /api/events/{event_id}/export.csv`

## Public participant

- `GET /api/public/events/{event_code}`
- `POST /api/public/events/{event_code}/join`
- `GET /api/public/events/{event_code}/state`
- `POST /api/public/questions/{question_id}/responses`

## Presentation and realtime

- `GET /api/presentation/{token}/state`
- `GET /api/events/{event_id}/qr.png`
- `WS /ws/events/{event_id}`

Role-specific state builders prevent participant and presentation clients from seeing
statistics before reveal.
