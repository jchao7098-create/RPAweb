// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import router from './index'

describe('user management route scopes', () => {
  it('enables all-platform reads only for development progress management', () => {
    const userRoutes = router.options.routes.find((route) => route.name === 'main').children
    const developmentRoute = userRoutes.find((route) => route.name === 'UserDevelopmentManagement')
    const requirementRoute = userRoutes.find((route) => route.name === 'UserRequirementReview')

    expect(developmentRoute.props).toMatchObject({
      apiPrefix: '/user/manage',
      selfService: true,
      readScope: 'all',
    })
    expect(requirementRoute.props).not.toHaveProperty('readScope')
  })
})
