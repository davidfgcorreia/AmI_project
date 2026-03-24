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
        placeholder="Search products..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Search products"
      />
      <button type="submit" className="btn-primary btn-icon" aria-label="Search">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
      </button>
      <button
        type="button"
        className={`voice-btn ${listening ? 'listening' : ''}`}
        onClick={listening ? stopListening : startListening}
        aria-label={listening ? 'Stop listening' : 'Voice search'}
        title="Voice search"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z"/></svg>
      </button>
    </form>
  );
}
