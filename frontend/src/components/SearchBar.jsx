/**
 * SearchBar - text + voice search for products.
 */
import React, { useState, useCallback } from 'react';
import useVoiceSearch from '../hooks/useVoiceSearch';

export default function SearchBar({ onSearch }) {
  const [query, setQuery] = useState('');

  const handleVoiceResult = useCallback((transcript) => {
    setQuery(transcript);
    onSearch(transcript);
  }, [onSearch]);

  const { listening, startListening, stopListening } = useVoiceSearch(handleVoiceResult);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim());
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="Search products…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Search products"
      />
      <button type="submit" className="btn-primary btn-icon" aria-label="Search">
        🔍
      </button>
      <button
        type="button"
        className={`voice-btn ${listening ? 'listening' : ''}`}
        onClick={listening ? stopListening : startListening}
        aria-label={listening ? 'Stop listening' : 'Voice search'}
        title="Voice search"
      >
        🎤
      </button>
    </form>
  );
}
