import { test } from 'node:test';
import assert from 'node:assert/strict';
import { arrange, fileUrl, mergeDouban, normalizeQuery, placeholderHue, primaryAuthor, withOpened } from './shelf.js';

const book = (key, title, extra = {}) => ({ key, title, author: null, doubanId: null, aliases: [], text: '', ...extra });
const BOOKS = [
  book('db:1', '人月神话', { author: '[美] 弗雷德里克·布鲁克斯', doubanId: '1' }),
  book('db:2', '神话与人', { doubanId: '2', aliases: ['22'] }),
  book('db:3', '茶馆', { author: '王笛', doubanId: '3', text: '成都的茶馆里谈人月' }),
  book('db:4', '明朝那些事儿', { author: '当年明月', doubanId: '4' }),
  book('wr:5', '人月神话（果麦经典）'),
];
const keys = (list) => list.map((b) => b.key);

test('an empty search lists opened books first, latest first, then the rest in catalog order', () => {
  const { recent, all } = arrange(BOOKS, '  ', { 'db:4': 100, 'db:2': 200 });
  assert.deepEqual(keys(recent), ['db:2', 'db:4']);
  assert.deepEqual(keys(all), ['db:1', 'db:3', 'wr:5']);
});

test('a title that starts with the query outranks one that only contains it', () => {
  assert.deepEqual(keys(arrange(BOOKS, '神话', {}).all), ['db:2', 'db:1', 'wr:5']);
});

test('among equal matches an opened book comes first', () => {
  const { recent, all } = arrange(BOOKS, '人月', { 'wr:5': 1 });
  assert.deepEqual(recent, []);
  assert.deepEqual(keys(all), ['wr:5', 'db:1', 'db:3']);
});

test('an author match and a note-text match come after title matches', () => {
  assert.deepEqual(keys(arrange(BOOKS, '明', {}).all), ['db:4']);
  assert.deepEqual(keys(arrange(BOOKS, '月', {}).all), ['db:1', 'wr:5', 'db:4', 'db:3']);
});

test('the query ignores 书名号, spaces and case', () => {
  assert.equal(normalizeQuery(' 《人月 神话》: AB '), '人月神话：ab');
  assert.deepEqual(keys(arrange(BOOKS, '《人月 神话》', {}).all), ['db:1', 'wr:5']);
});

test('Douban results already on the shelf are dropped, aliases included', () => {
  const results = [book('db:1', '人月神话', { doubanId: '1' }), book('db:22', '神话与人', { doubanId: '22' }),
    book('db:9', '人月神话（纪念版）', { doubanId: '9' })];
  assert.deepEqual(keys(mergeDouban(BOOKS, results)), ['db:9']);
});

test('the placeholder colour is stable for a title', () => {
  const hue = placeholderHue('人月神话');
  assert.ok(Number.isInteger(hue) && hue >= 0 && hue < 360);
  assert.equal(placeholderHue('人月神话'), hue);
  assert.notEqual(placeholderHue('茶馆'), hue);
});

test('a local file becomes a file URL with each path part encoded', () => {
  assert.equal(fileUrl('/Users/a b/封面/人月#1.jpg'), 'file:///Users/a%20b/%E5%B0%81%E9%9D%A2/%E4%BA%BA%E6%9C%88%231.jpg');
});

test('Douban results that are another edition of a shelf book (same title and author) are dropped', () => {
  const results = [
    book('db:7', '人月神话', { doubanId: '7', author: '弗雷德里克・布鲁克斯' }),
    book('db:8', '人月神话', { doubanId: '8', author: '另一个人' }),
  ];
  assert.deepEqual(keys(mergeDouban(BOOKS, results)), ['db:8']);
});

test('the first author is compared without nationality marks, spaces or dot styles', () => {
  assert.equal(primaryAuthor('[美] 弗雷德里克.布鲁克斯 / 汪颖'), '弗雷德里克·布鲁克斯');
  assert.equal(primaryAuthor('弗雷德里克・布鲁克斯'), '弗雷德里克·布鲁克斯');
  assert.equal(primaryAuthor(null), '');
});

test('a book opened from Douban joins the shelf, so it shows among the recent ones', () => {
  const extra = book('db:9', '凤凰架构', { doubanId: '9' });
  const shelf = withOpened(BOOKS, [extra, BOOKS[0]]);
  assert.deepEqual(keys(shelf), ['db:9', ...keys(BOOKS)]);
  assert.deepEqual(keys(arrange(shelf, '', { 'db:9': 5 }).recent), ['db:9']);
});
