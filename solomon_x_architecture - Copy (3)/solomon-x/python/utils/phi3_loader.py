import os
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger("solomon.utils.phi3")

class ReRanker:
    """
    Candidate memories re-ranker utilizing Phi-3 completions or fallback word overlap counts.
    """
    def __init__(self, model_instance=None):
        self.model = model_instance

    def rerank(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Reranks candidates based on relevance to query.
        Uses llama-cpp-python if loaded, otherwise falls back to word overlap.
        """
        if self.model:
            try:
                ranked = []
                for c in candidates:
                    content = c.get("content", "")
                    prompt = (
                        f"<|system|>\nRate the relevance of the document to the query on a scale of 0 to 10. "
                        f"Output only the number.\n<|user|>\nQuery: {query}\nDocument: {content}\n<|assistant|>\n"
                    )
                    output = self.model(prompt, max_tokens=4, temperature=0.0)
                    text = output["choices"][0]["text"].strip()
                    try:
                        score = float(text) / 10.0
                    except ValueError:
                        score = 0.5
                    
                    c["rerank_score"] = score
                    ranked.append(c)
                ranked.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
                return ranked
            except Exception as e:
                logger.warning(f"Phi-3 re-rank execution failed: {e}. Falling back to keyword overlap.")

        # Fallback keyword overlap re-ranking
        logger.info("Using software fallback keyword overlap re-ranker.")
        query_words = set(query.lower().split())
        
        ranked = []
        for c in candidates:
            content = c.get("content", "").lower()
            if not content:
                content = json.dumps(c.get("metadata", {}))
                
            content_words = set(content.split())
            overlap = query_words.intersection(content_words)
            
            # Re-rank score combines word overlap with existing salience/novelty
            overlap_score = len(overlap) / (len(query_words) + 1e-9)
            base_score = (c.get("salience", 0.5) + c.get("novelty", 0.5)) / 2.0
            
            c["rerank_score"] = 0.7 * overlap_score + 0.3 * base_score
            ranked.append(c)
            
        ranked.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return ranked

class Phi3Loader:
    """
    GGUF model loader for Phi-3-mini 4-bit.
    Tries to import llama-cpp-python and load the local model file.
    If not available or file is missing, returns a fallback stub.
    """
    def __init__(self, model_path: str = "./models/phi-3-mini-4bit.gguf") -> None:
        self.model_path = model_path
        self.model = None
        self.load_model()

    def load_model(self) -> None:
        target_path = self.model_path
        if not os.path.isabs(target_path) and not os.path.exists(target_path):
            target_path = os.path.join(os.getcwd(), "models", "phi-3-mini-4bit.gguf")

        if not os.path.exists(target_path):
            logger.warning(f"Phi-3 GGUF model file not found at '{target_path}'. Running re-ranker in stub mode.")
            return

        try:
            from llama_cpp import Llama
            logger.info(f"Loading Phi-3 GGUF model from {target_path}...")
            # Load model onto CPU/GPU. RTX 4060 has GPU acceleration if n_gpu_layers > 0
            self.model = Llama(
                model_path=target_path,
                n_ctx=2048,
                n_threads=4,
                n_gpu_layers=32 # Offload layers to GPU
            )
            logger.info("Phi-3 model loaded successfully.")
        except ImportError:
            logger.warning("llama-cpp-python not installed. Re-ranker will operate in word-overlap fallback mode.")
        except Exception as e:
            logger.error(f"Error loading model: {e}")

    def get_reranker(self) -> ReRanker:
        return ReRanker(self.model)
