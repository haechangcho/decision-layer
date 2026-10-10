import { defineConfig } from 'vitepress'

const github = 'https://github.com/haechangcho/decision-layer'

export default defineConfig({
  title: 'Decision Layer',
  description: 'Connect governed metrics to reusable analysis procedures.',
  lang: 'en-US',
  ignoreDeadLinks: 'localhostLinks',
  srcExclude: [
    'README.md', 'GETTING_STARTED.md', 'MVP_PLAN.md', 'REFERENCES.md',
    'PRODUCT_UX_IMPLEMENTATION_PLAN.ko.md', 'PRODUCT_UX_MILESTONES.ko.md',
    'SOURCE_CONNECTION_DESIGN.ko.md', 'internal/**', 'design/**', 'research/**',
    'assets/README.md'
  ],
  themeConfig: {
    siteTitle: 'Decision Layer',
    i18nRouting: false,
    search: {
      provider: 'local',
      options: {
        locales: {
          ko: {
            translations: {
              button: { buttonText: '문서 검색', buttonAriaLabel: '문서 검색' },
              modal: {
                displayDetails: '자세히 보기', resetButtonTitle: '검색 지우기', backButtonTitle: '검색 닫기', noResultsText: '검색 결과가 없습니다',
                footer: { selectText: '선택', selectKeyAriaLabel: 'Enter', navigateText: '이동', navigateUpKeyAriaLabel: '위쪽 화살표', navigateDownKeyAriaLabel: '아래쪽 화살표', closeText: '닫기', closeKeyAriaLabel: 'Escape' }
              }
            }
          }
        }
      }
    },
    socialLinks: [{ icon: 'github', link: github }],
    editLink: { pattern: `${github}/edit/main/docs/:path`, text: 'Edit this page' },
    outline: { level: [2, 3], label: 'On this page' },
    nav: [
      { text: 'Guides', link: '/' },
      { text: 'Web app', link: 'http://localhost:3000' },
      { text: 'GitHub', link: github }
    ],
    sidebar: [
      { text: 'Get started', items: [
        { text: 'Quickstart', link: '/' },
        { text: 'Connect Cube', link: '/guides/cube' },
        { text: 'Connect dbt Semantic Layer', link: '/guides/dbt' },
        { text: 'Connect an AI client', link: '/guides/mcp' }
      ] },
      { text: 'Use Decision Layer', items: [
        { text: 'Recipes', link: '/guides/recipes' },
        { text: 'Runs and evidence', link: '/guides/runs' }
      ] },
      { text: 'Develop', items: [
        { text: 'Local development', link: '/guides/development' },
        { text: 'Add a Method', link: '/guides/methods' },
        { text: 'Testing', link: '/guides/testing' },
        { text: 'Evaluation', link: '/guides/evaluation' },
        { text: 'Interface design', link: '/guides/design-system' }
      ] },
      { text: 'Reference', items: [
        { text: 'Product context', link: '/PRODUCT_CONTEXT' },
        { text: 'Architecture', link: '/ARCHITECTURE' },
        { text: 'Decisions', link: '/DECISIONS' }
      ] }
    ]
  },
  locales: {
    root: { label: 'English', lang: 'en-US', link: '/' },
    ko: {
      label: '한국어', lang: 'ko-KR', link: '/ko/',
      themeConfig: {
        nav: [
          { text: '가이드', link: '/ko/' },
          { text: '웹 앱', link: 'http://localhost:3000' },
          { text: 'GitHub', link: github }
        ],
        sidebar: [
          { text: '시작하기', items: [
            { text: '빠른 시작', link: '/ko/' },
            { text: 'Cube 연결', link: '/ko/guides/cube' },
            { text: 'dbt Semantic Layer 연결', link: '/ko/guides/dbt' },
            { text: 'AI 도구 연결', link: '/ko/guides/mcp' }
          ] },
          { text: '분석 사용하기', items: [
            { text: 'Recipe 만들기', link: '/ko/guides/recipes' },
            { text: '실행 기록과 근거', link: '/ko/guides/runs' }
          ] },
          { text: '개발과 기여', items: [
            { text: 'Method 추가', link: '/ko/guides/methods' },
            { text: '개발 환경', link: '/ko/guides/development' },
            { text: '테스트', link: '/ko/guides/testing' },
            { text: '분석 품질 평가', link: '/ko/guides/evaluation' },
            { text: '인터페이스 디자인', link: '/ko/guides/design-system' },
            { text: '아키텍처', link: '/ko/ARCHITECTURE' }
          ] }
        ],
        outline: { level: [2, 3], label: '이 페이지에서' },
        editLink: { pattern: `${github}/edit/main/docs/:path`, text: 'GitHub에서 수정' },
        docFooter: { prev: '이전', next: '다음' },
        lastUpdated: { text: '마지막 수정' },
        returnToTopLabel: '맨 위로',
        sidebarMenuLabel: '메뉴',
        darkModeSwitchLabel: '화면 테마'
      }
    }
  }
})
