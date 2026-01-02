
function testParseHFUrl(input) {
    let repoId = input;
    let filename = "";

    if (input.includes('huggingface.co/')) {
        try {
            const url = new URL(input);
            const pathParts = url.pathname.split('/').filter(p => p);

            if (pathParts.length >= 2) {
                repoId = `${pathParts[0]}/${pathParts[1]}`;

                if (pathParts.includes('blob') || pathParts.includes('resolve')) {
                    const typeIdx = pathParts.indexOf('blob') !== -1 ? pathParts.indexOf('blob') : pathParts.indexOf('resolve');
                    if (pathParts.length > typeIdx + 2) {
                        filename = pathParts.slice(typeIdx + 2).join('/');
                    }
                }
            }
        } catch (e) {
            console.error('URL parsing failed:', e);
        }
    }
    return { repoId, filename };
}

const testUrl = "https://huggingface.co/LiquidAI/LFM2-2.6B-Exp-GGUF/blob/main/LFM2-2.6B-Exp-Q4_K_M.gguf";
const result = testParseHFUrl(testUrl);
console.log(`Input: ${testUrl}`);
console.log(`Repo ID: ${result.repoId}`);
console.log(`Filename: ${result.filename}`);

if (result.repoId === "LiquidAI/LFM2-2.6B-Exp-GGUF" && result.filename === "LFM2-2.6B-Exp-Q4_K_M.gguf") {
    console.log("SUCCESS: URL parsed correctly.");
} else {
    console.log("FAILURE: URL parsing failed.");
    process.exit(1);
}
