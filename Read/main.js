const $root = document.querySelector('#root')
const catalog = window.READ_CATALOG || []
const books = window.READ_BOOKS || {}
let onScroll = null

const storeKey = (id) => `read:${id}`

const readStore = (id) => {
  try {
    return JSON.parse(localStorage.getItem(storeKey(id)) || 'null')
  } catch {
    return null
  }
}

const writeStore = (id, data) => {
  localStorage.setItem(storeKey(id), JSON.stringify(data))
}

const escapeHtml = (value) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')

const parseHash = () => {
  const raw = decodeURIComponent(location.hash.replace(/^#\/?/, ''))
  if (!raw) return { view: 'library' }
  const [bookId, chapterId, sentId] = raw.split('/')
  if (!books[bookId]) return { view: 'library' }
  return { view: 'reader', bookId, chapterId, sentId }
}

const setHash = (bookId, chapterId, sentId) => {
  const next = sentId
    ? `#/${bookId}/${chapterId}/${sentId}`
    : chapterId ? `#/${bookId}/${chapterId}` : `#/${bookId}`
  if (location.hash !== next) location.hash = next
}

const renderLibrary = () => {
  document.title = 'Read'
  $root.innerHTML = `
    <main class="library">
      <header class="library-head">
        <p class="library-kicker">Read</p>
        <h1>书架</h1>
      </header>
      <div class="book-list">
        ${catalog.map((book) => `
          <button class="book-card" type="button" data-open="${escapeHtml(book.id)}">
            <div class="book-card-title">${escapeHtml(book.title)}</div>
            <div class="book-card-meta">${escapeHtml(book.author)}${book.translatorZh ? ` · ${escapeHtml(book.translatorZh)} 译` : ''}</div>
            <div class="book-card-note">${escapeHtml(book.note || '')}</div>
          </button>
        `).join('')}
      </div>
    </main>
  `
  $root.querySelectorAll('[data-open]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-open')
      const saved = readStore(id)
      const book = books[id]
      const chapterId = saved?.chapterId || book?.chapters?.[0]?.id
      setHash(id, chapterId)
    })
  })
}

const cardMeta = (book, sentence) => {
  if (!sentence?.zh) return book.hasZh ? '暂无对应译文' : '尚未导入中译本'
  const by = book.translatorZh ? `${book.translatorZh} 译` : '译文'
  if (sentence.scope === 'block') return `${by} · 对应段落`
  if (sentence.scope === 'group') return `${by} · 对应句组`
  return by
}

const renderReader = (bookId, chapterId, sentId) => {
  const book = books[bookId]
  if (!book) {
    renderLibrary()
    return
  }
  const chapters = book.chapters
  const saved = readStore(bookId)
  const current = chapters.find((ch) => ch.id === chapterId) || chapters.find((ch) => ch.id === saved?.chapterId) || chapters[0]
  document.title = `${book.title} · Read`
  writeStore(bookId, { chapterId: current.id, sentId: saved?.sentId || null })

  $root.innerHTML = `
    <div class="reader">
      <header class="topbar">
        <div class="topbar-inner">
          <button class="ghost" type="button" data-back>书架</button>
          <div class="topbar-title">${escapeHtml(book.title)}</div>
          <select class="chapter-select" aria-label="章节">
            ${chapters.map((ch) => `
              <option value="${escapeHtml(ch.id)}" ${ch.id === current.id ? 'selected' : ''}>
                ${escapeHtml(ch.title)}
              </option>
            `).join('')}
          </select>
        </div>
      </header>
      <div class="scroller">
        <article class="article" data-article>
          <h2 class="chapter-heading">
            ${escapeHtml(current.title)}
            ${current.titleZh ? `<small>${escapeHtml(current.titleZh)}</small>` : ''}
          </h2>
          ${current.paragraphs.map((para, pIndex) => renderPara(book, para, pIndex)).join('')}
        </article>
      </div>
    </div>
  `

  const $article = $root.querySelector('[data-article]')
  $root.querySelector('[data-back]').addEventListener('click', () => {
    location.hash = ''
  })
  $root.querySelector('.chapter-select').addEventListener('change', (event) => {
    setHash(bookId, event.target.value)
  })

  $article.addEventListener('click', (event) => {
    const $sent = event.target.closest('.sent')
    if (!$sent || $sent.classList.contains('is-mute')) return
    const already = $sent.classList.contains('is-open')
    closeCards($article)
    if (already) {
      writeStore(bookId, { chapterId: current.id, sentId: null })
      return
    }
    openCard(book, $sent)
    writeStore(bookId, { chapterId: current.id, sentId: $sent.dataset.sid })
  })

  observeFocus($article)

  const restoreId = sentId || (saved?.chapterId === current.id ? saved.sentId : null)
  if (restoreId) {
    const $sent = $article.querySelector(`[data-sid="${CSS.escape(restoreId)}"]`)
    if ($sent) {
      openCard(book, $sent)
      $sent.scrollIntoView({ block: 'center' })
    }
  }
}

const renderPara = (book, para, pIndex) => {
  if (para.type === 'break') return '<div class="break"></div>'
  const sentences = (para.sentences || []).map((sent) => (
    typeof sent === 'string' ? { en: sent, zh: '', scope: 'none' } : sent
  ))
  if (!sentences.length && para.en) sentences.push({ en: para.en, zh: para.zh || '', scope: para.zh ? 'block' : 'none' })
  if (!sentences.length) return ''
  const html = sentences.map((sent, sIndex) => {
    const sid = `${pIndex}-${sIndex}`
    const mute = !book.hasZh
    return `<span class="sent${mute ? ' is-mute' : ''}" data-sid="${sid}" data-p="${pIndex}" data-s="${sIndex}">${escapeHtml(sent.en)}</span> `
  }).join('')
  return `<p class="para" data-p="${pIndex}">${html}</p>`
}

const closeCards = (scope) => {
  scope.querySelectorAll('.trans-card').forEach((node) => node.remove())
  scope.querySelectorAll('.sent.is-open').forEach((node) => node.classList.remove('is-open'))
}

const openCard = (book, $sent) => {
  $sent.classList.add('is-open')
  $sent.closest('.para')?.classList.add('is-focus')
  const pIndex = Number($sent.dataset.p)
  const sIndex = Number($sent.dataset.s)
  const chapterId = $root.querySelector('.chapter-select')?.value
  const chapter = book.chapters.find((ch) => ch.id === chapterId)
  const sentence = chapter?.paragraphs?.[pIndex]?.sentences?.[sIndex]
  const $card = document.createElement('span')
  $card.className = 'trans-card'
  $card.innerHTML = `
    <div class="trans-card-meta">${escapeHtml(cardMeta(book, sentence))}</div>
    <div class="trans-card-body">${sentence?.zh ? escapeHtml(sentence.zh) : '这句还没有对齐到中文。'}</div>
  `
  $sent.after($card)
}

const observeFocus = ($article) => {
  const paras = [...$article.querySelectorAll('.para')]
  if (!paras.length) return
  const sync = () => {
    const mid = innerHeight * 0.38
    let best = paras[0]
    let bestDist = Infinity
    for (const $para of paras) {
      const rect = $para.getBoundingClientRect()
      if (rect.bottom < 80 || rect.top > innerHeight - 40) continue
      const dist = Math.abs((rect.top + rect.bottom) / 2 - mid)
      if (dist < bestDist) {
        best = $para
        bestDist = dist
      }
    }
    const opened = $article.querySelector('.sent.is-open')
    paras.forEach(($para) => $para.classList.toggle('is-focus', $para === best || (opened && $para.contains(opened))))
  }
  let ticking = false
  if (onScroll) document.removeEventListener('scroll', onScroll)
  onScroll = () => {
    if (ticking) return
    ticking = true
    requestAnimationFrame(() => {
      ticking = false
      sync()
    })
  }
  document.addEventListener('scroll', onScroll, { passive: true })
  sync()
}

const route = () => {
  const state = parseHash()
  if (state.view === 'reader') renderReader(state.bookId, state.chapterId, state.sentId)
  else renderLibrary()
}

window.addEventListener('hashchange', route)
route()
