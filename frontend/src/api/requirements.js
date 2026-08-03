import http from './http'

export function fetchMyRequirements(userId) {
  return http.get('/user/get_my_requirements', {
    params: { user_id: userId },
  })
}

export function updateMyRequirement({
  id,
  userId,
  title,
  description,
  department,
  requester,
  priority,
  feedbackTime,
  expectedFinishTime,
  platform,
  operationLink,
  account,
  password,
}) {
  return http.patch(`/user/requirements/${id}`, {
    user_id: userId,
    title,
    description,
    department,
    requester,
    priority,
    feedback_time: feedbackTime,
    expected_finish_time: expectedFinishTime,
    platform,
    operation_link: operationLink,
    account,
    password,
  })
}
