export function createSSEParser(onEvent: (event: {name: string; id: string; data: any}) => void): (text: string) => void;
