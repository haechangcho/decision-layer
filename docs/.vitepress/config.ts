import { defineConfig } from 'vitepress'

const github = 'https://github.com/haechangcho/decision-layer'

function sidebar(locale: '' | 'ko') {
  const ko = locale === 'ko'
  const prefix = ko ? '/ko' : ''
  const item = (en: string, kr: string, path: string) => ({ text: ko ? kr : en, link: prefix + path })
  return [
    { text: ko ? '시작하기' : 'Get started', items: [
      item('Start here', '시작하기', '/'),
      item('Run the sample', '샘플 실행', '/guides/quickstart'),
      item('Connect Cube', 'Cube 연결', '/guides/cube'),
      item('Connect dbt Semantic Layer', 'dbt Semantic Layer 연결', '/guides/dbt'),
      item('Connect an AI client', 'AI 도구 연결', '/guides/mcp')
    ] },
    { text: ko ? '분석 사용하기' : 'Use Decision Layer', items: [
      item('Recipes', 'Recipe 만들기', '/guides/recipes'),
      item('Runs and evidence', '실행 기록과 근거', '/guides/runs')
    ] },
    { text: ko ? '개발과 기여' : 'Develop', items: [
      item('First Method', '첫 Method 개발', '/guides/methods'),
      item('Local development', '개발 환경', '/guides/development'),
      item('Testing', '테스트', '/guides/testing')
    ] },
    { text: ko ? '참고 문서' : 'Reference', collapsed: true, items: [
      item('Method contract', 'Method 계약', '/reference/method-contract'),
      item('Architecture', '아키텍처', '/ARCHITECTURE')
    ] }
  ]
}

export default defineConfig({
  title: 'Decision Layer',
  description: 'Connect governed metrics to reusable analysis procedures.',
  lang: 'en-US',
  ignoreDeadLinks: 'localhostLinks',
  srcExclude: [
    'README.md', 'GETTING_STARTED.md', 'MVP_PLAN.md', 'REFERENCES.md',
    'PRODUCT_CONTEXT.md', 'DECISIONS.md',
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
      { text: 'GitHub', link: github }
    ],
    sidebar: sidebar('')
  },
  locales: {
    root: { label: 'English', lang: 'en-US', link: '/' },
    ko: {
      label: '한국어', lang: 'ko-KR', link: '/ko/',
      themeConfig: {
        nav: [
          { text: '가이드', link: '/ko/' },
          { text: 'GitHub', link: github }
        ],
        sidebar: sidebar('ko'),
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
