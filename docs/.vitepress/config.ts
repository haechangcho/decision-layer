import { defineConfig } from 'vitepress'
import { notebookDownloads } from './notebooks.mjs'

const github = 'https://github.com/haechangcho/decision-layer'

function sidebar(locale: '' | 'ko') {
  const ko = locale === 'ko'
  const prefix = ko ? '/ko' : ''
  const item = (en: string, kr: string, path: string) => ({ text: ko ? kr : en, link: prefix + path })
  return [
    { text: ko ? '시작하기' : 'Get started', items: [
      item('Introduction', '소개', '/'),
      item('Install and start', '설치하고 시작하기', '/guides/quickstart'),
      item('Connect Cube', 'Cube 연결', '/guides/cube'),
      item('Connect an AI client', 'AI 도구 연결', '/guides/mcp')
    ] },
    { text: ko ? '분석 사용하기' : 'Use Decision Layer', items: [
      item('Recipes', 'Recipe 만들기', '/guides/recipes'),
      item('Runs and evidence', '실행 기록과 근거', '/guides/runs')
    ] },
    { text: ko ? 'Method 확장하기' : 'Extend Methods', items: [
      item('Understand Methods', 'Method 이해하기', '/guides/methods'),
      item('Connect a Python function', 'Python Method 만들기', '/tutorials/write-your-method'),
      item('Register in a project', '프로젝트에 등록하기', '/guides/method-projects'),
      item('Method API', 'Method API', '/reference/method-contract')
    ] },
    { text: ko ? '제품 개발' : 'Product development', collapsed: true, items: [
      item('Development and tests', '개발 환경과 테스트', '/guides/development'),
      item('Code structure', '코드 구조', '/ARCHITECTURE')
    ] }
  ]
}

export default defineConfig({
  vite: { plugins: [notebookDownloads()] },
  title: 'Decision Layer',
  description: 'Connect governed metrics to reusable analysis procedures.',
  lang: 'en-US',
  ignoreDeadLinks: 'localhostLinks',
  srcExclude: [
    'README.md', 'GETTING_STARTED.md', 'MVP_PLAN.md', 'REFERENCES.md',
    'PRODUCT_CONTEXT.md', 'DECISIONS.md', 'PRD.md',
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
