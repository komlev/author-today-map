// See https://observablehq.com/framework/config for documentation.
export default {
  title: "Литературная карта Author.Today",

  pages: [
    {
      name: "Обзор",
      pages: [
        {name: "Жанры и теги", path: "/genres"},
        {name: "Статус и тип текста", path: "/structure"},
        {name: "Серии и одиночные книги", path: "/series"},
        {name: "Качество вовлечённости", path: "/engagement"},
        {name: "Продуктивность авторов", path: "/authors"},
        {name: "Накрутка", path: "/nakrutka"},
        {name: "Соавторство", path: "/coauthors"},
        {name: "Рост во времени", path: "/growth"}
      ]
    }
  ],

  root: "src",
  theme: "dashboard",

  // src/robots.txt isn't linked from any page, so it wouldn't otherwise be
  // discovered by the build's page/asset crawl — dynamicPaths forces it in.
  dynamicPaths: ["/robots.txt"],

  // Framework hardcodes "Previous page"/"Next page" and "Built with Observable"
  // in English via CSS ::before content; override both here for a fully
  // Russian-language UI.
  head: `<style>
    #observablehq-footer nav a[rel=prev]::before { content: "Предыдущая страница"; }
    #observablehq-footer nav a[rel=next]::before { content: "Следующая страница"; }
  </style>`,
  footer: `Сделано с помощью <a href="https://observablehq.com/" target="_blank">Observable</a>.`,
};
