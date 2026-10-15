const NEVER_CAPITALIZE_SET = new Set(["of", "the", "a"]);
const INTIALS_REGEX = /[a-z]\.(?:[a-z]\.)+/;

const toTitleCase = (phrase) => {
  if (phrase == null) {
    return phrase;
  }
  return phrase
    .toLowerCase()
    .split(' ')
    .map((word, index) => {
        if (index != 0 && NEVER_CAPITALIZE_SET.has(word)) {
            return word;
        } 
        if (INTIALS_REGEX.test(word)) {
            return word.toUpperCase();
        }
        return word.charAt(0).toUpperCase() + word.slice(1)
    })
    .join(' ');
};

export {
    toTitleCase
}
// Fire dates come from the pipeline as ISO strings in UTC. Sources that only
// record the day store midnight UTC, so show those without a time.
const formatFireDate = (iso) => {
  if (!iso) {
    return null;
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  const dateOnly =
    date.getUTCHours() === 0 && date.getUTCMinutes() === 0 && date.getUTCSeconds() === 0;
  if (dateOnly) {
    return date.toLocaleDateString(undefined, { dateStyle: "medium", timeZone: "UTC" });
  }
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
};

export {
    formatFireDate
}
