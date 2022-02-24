const loader = document.querySelector('#loader');
const home = document.querySelector('#home');
const [homeInput, mainForm] = ['input', 'form'].map(sel => home.querySelector(sel));

const searchView = document.querySelector('#search-view');
const [searchContent, searchViewForm, searchViewInput, resultInfo, moreDiv,
    chartContainer, settings, settingsContainer] =
    ['.search-content', '.menu form', '.menu input', '#result-info', '.more',
        '#chartContainer', '.settings form', '.settings']
        .map(sel => searchView.querySelector(sel));

const SEARCH_ENDPOINT = '/search';
const SETTINGS_ENDPOINT = '/settings';
const pageLimit = 10;
let mode = sessionStorage.getItem('mode');
if (mode === null) {
    sessionStorage.setItem('mode', '3');
    mode = 3;
}
settings['mode'].value = mode;

let chart = null;
let chartVisible = false;
let settingsVisible = false;
let curSVDOrd = -1;


fetch(SETTINGS_ENDPOINT)
    .then(resp => resp.json())
    .then(data => {
        settings.querySelector('input[type="number"]').value = data['k'];
        curSVDOrd = data['k'];
    })
    .catch(err => {
        console.log(err);
        settings.querySelector('input[type="number"]').value = -1;
    })


let isAtHome = true;
let pageNumber = 1;
const queryCache = {
    links: [],
    titles: [],
    contents: [],
    correlations: [],
    count: 0,
    query: ''
}

mainForm.addEventListener('submit', e => {
    e.preventDefault();
    handleSearchQuery(homeInput.value);
});

searchViewForm.addEventListener('submit', e => {
    e.preventDefault();
    handleSearchQuery(searchViewInput.value);
});


settings.addEventListener('submit', async e => {
    e.preventDefault();
    mode = settings['mode'].value;
    k = settings['svd-order'].value;
    sessionStorage.setItem('mode', mode);
    if (k != curSVDOrd) {
        const resp = await fetch(SETTINGS_ENDPOINT, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ order: +k })
        }).then(x => x.json());

        console.log(resp);
        if (resp['computed'] === false)
            popup('this may take a while');

        curSVDOrd = k;
    }
    toggleSettings();
});

async function handleSearchQuery(query, offset = 0) {
    query = query.trim();
    if (query.length == 0)
        return;

    const url = `${SEARCH_ENDPOINT}?q=${query}&offset=${offset}&mode=${mode}`;
    try {
        loader.style.visibility = 'visible';
        const data = await fetch(url).then(resp => resp.json());
        setUpDisplayView();
        searchContent.innerHTML = '';
        if (offset === 0) {
            queryCache.titles = [];
            queryCache.contents = [];
            queryCache.links = [];
            queryCache.correlations = [];
            queryCache.query = query;
            pageNumber = 1;
        }

        if (chartVisible)
            toggleChart();
        chart = null;


        searchViewInput.value = query;
        const { results_count: count, links, titles, contents, correlations: correls, time } = JSON.parse(data);
        resultInfo.textContent = `About ${count} results (${time} seconds)`

        queryCache.titles.push(...titles);
        queryCache.contents.push(...contents);
        queryCache.links.push(...links);
        queryCache.correlations.push(...correls);
        queryCache.count = count;
        addSearchContent(offset);
        fixTextContents();
        setUpNextPages();
    } catch (err) {
        console.log(err);
        resultInfo.textContent = 'Error :( are you sure you\'ve typed valid english words? (check console for more info)';
    }
    finally {
        loader.style.visibility = 'hidden';
    }
}

function addSearchContent(offset) {
    const { titles, contents, links, correlations, count } = queryCache;

    for (let i = offset; i < links.length && i < offset + pageLimit; i++) {
        const li = document.createElement('li');
        li.innerHTML = `
            <h5 class="correlation">${Math.round(correlations[i] * 10000) / 100}% </h5>
            <a class="link" href="${links[i]}">${links[i]}</a>
            <a href="${links[i]}" class="title">${titles[i]}</a>
            <h4 class="site-content">${contents[i]} ...</h4>`;

        searchContent.appendChild(li);
    }
}

function setUpNextPages() {
    let lis = '';
    for (let i = Math.max(0, pageNumber - 5); i < Math.min(10 + Math.max(0, pageNumber - 6), queryCache.count / pageLimit); i++)
        lis += `<li data-idx="${i + 1}"><a href="#"><div>e</div><div>${i + 1}</div></a></li>\n`;

    if (pageNumber - 5 > 0)
        lis = `<li data-idx="1"><a href="#"><div>e</div><div>1</div></a></li>\n` + lis;

    moreDiv.innerHTML = `<span>S</span><ul>${lis}</ul><span>archVD</span>`;
    if (pageNumber * pageLimit < queryCache.count) {
        moreDiv.innerHTML += `
            <span class="next"><a href="#">
            <div><i class="fas fa-chevron-right"></i></div>
            <div>Next</div>
            </a></span>`;

        moreDiv.querySelector('.next').addEventListener('click', e => {
            e.preventDefault();
            changePage(-1);
        })
    }

    moreDiv.querySelectorAll('li').forEach(li =>
        li.addEventListener('click', e => {
            e.preventDefault();
            changePage(+li.dataset.idx);
        }));

    moreDiv.querySelector(`li[data-idx="${pageNumber}"] div:first-child`).classList.add('current-page');
}


function changePage(num) {
    if (num === -1)
        num = pageNumber + 1;


    pageNumber = num;

    if (num * pageLimit > queryCache.links.length)
        handleSearchQuery(queryCache.query, queryCache.links.length);
    else {
        searchContent.innerHTML = '';
        addSearchContent((num - 1) * pageLimit);
        fixTextContents();
        setUpNextPages();
    }
}


function fixTextContents() {
    const maxWidth = searchContent.clientWidth;
    searchContent.querySelectorAll('li').forEach(li => {
        const title = li.querySelector('.title');
        hideOverflowingText(title, maxWidth);
    });
}

function hideOverflowingText(element, maxWidth) {
    const textContent = element.textContent;
    element.textContent = '';
    for (let word of textContent.split(' ')) {
        const tmp = element.textContent;
        element.textContent += word + ' ';
        if (element.clientWidth > 0.9 * maxWidth) {
            element.textContent = tmp;
            element.textContent += ' ...';
            break;
        }
    }
}

function setUpDisplayView() {
    if (isAtHome) {
        isAtHome = false;
        home.style.display = 'none';
        homeInput.value = '';
        searchView.style.display = 'block';
    }
}


function toggleChart() {
    if (chart === null) {
        chart = new CanvasJS.Chart("chartContainer", {
            animationEnabled: true,
            theme: "light2",
            title: {
                text: "Correlation"
            },
            data: [{
                type: "line",
                dataPoints: queryCache.correlations.map(crl => { return { y: crl } })
            }]
        });
        chart.render();
    }

    chartVisible = !chartVisible;
    chartContainer.style.visibility = chartVisible ? 'visible' : 'hidden';
    const canvas = chartContainer.querySelector('canvas');
    document.querySelector('#chart-wrapper').style.height = `${chartVisible ? canvas.clientHeight + 20 : 0}px`;
}

function toggleSettings() {
    const cur = settingsContainer.style.display
    settingsContainer.style.display = cur === 'none' ? 'block' : 'none';
}


function popup(msg) {
    const popup = document.createElement('div');
    popup.classList.add('popup');
    popup.textContent = msg;
    document.body.appendChild(popup);
    setTimeout(() => popup.remove(), 9000);
}