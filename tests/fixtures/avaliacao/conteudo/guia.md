# Guia de Adaptação de Currículo — Pessoa Ficticia (conjunto de avaliação)

## 4. Cobertura de tecnologias

Toda tecnologia citada precisa estar presa a uma âncora.

- A vaga pede Kubernetes, o candidato tem Docker Compose → cite containerização e orquestração local, não diga Kubernetes.
- A vaga pede Kafka, o candidato tem RabbitMQ → cite mensageria assíncrona e eventos.

---

## 10. Currículo base (fonte de verdade)

```latex
\documentclass[a4paper,10pt]{article}
\usepackage[brazil]{babel}

\begin{document}

\section{Sobre}
Estudante de computação de exemplo que construiu APIs em \tech{Python} sobre \tech{PostgreSQL} e serviços com \tech{Docker Compose}. Já entregou filas com \tech{RabbitMQ}, interfaces em \tech{React} e pipelines de dados com \tech{Pandas}, sempre em projetos fictícios usados só para avaliar o gerador.

\section{Experiência}

\textbf{Desenvolvedora Estagiária, Empresa Exemplo Ltda, Divisão Dados} \hfill 2023 -- Presente
\begin{itemize}
    \item Construí uma API REST em \tech{Python} com \tech{Flask} sobre \tech{PostgreSQL} para cadastros internos.
    \item Implementei filas de processamento assíncrono com \tech{RabbitMQ} entre os serviços da equipe.
\end{itemize}

\vspace{2.5mm}
\textbf{Pesquisadora, Laboratório Exemplo, Visão e Borda} \hfill 2022 -- 2023
\begin{itemize}
    \item Desenvolvi reconhecimento de objetos com \tech{OpenCV} em hardware de borda do laboratório.
\end{itemize}

\section{Projetos}

\textbf{Projeto Alfa}, sistema de exemplo \hfill \href{https://example.invalid/alfa}{example.invalid/alfa}
\begin{itemize}
    \item Estruturei serviços com \tech{Docker Compose} e \tech{PostgreSQL} para um ambiente local reprodutível.
\end{itemize}

\vspace{2.5mm}
\textbf{Projeto Gama}, painel de exemplo \hfill \href{https://example.invalid/gama}{example.invalid/gama}
\begin{itemize}
    \item Construí uma interface em \tech{React} com \tech{TypeScript} que consome uma API interna de exemplo.
\end{itemize}

\vspace{2.5mm}
\textbf{Projeto Delta}, análise de exemplo \hfill \href{https://example.invalid/delta}{example.invalid/delta}
\begin{itemize}
    \item Modelei um pipeline de dados com \tech{Pandas} e \tech{Python} sobre arquivos públicos de exemplo.
\end{itemize}

\vspace{2.5mm}
\textbf{Projeto Epsilon}, borda de exemplo \hfill \href{https://example.invalid/epsilon}{example.invalid/epsilon}
\begin{itemize}
    \item Integrei sensores de exemplo por \tech{MQTT} com mensagens repassadas pelo \tech{RabbitMQ}.
\end{itemize}

\end{document}
```

versao em ingles: ```latex

\documentclass[a4paper,10pt]{article}
\usepackage[english]{babel}

\begin{document}

\section{About}
Example computing student who built APIs in \tech{Python} over \tech{PostgreSQL} and services with \tech{Docker Compose}. Delivered queues with \tech{RabbitMQ}, interfaces in \tech{React} and data pipelines with \tech{Pandas}, always in fictitious projects used only to evaluate the generator.

\section{Experience}

\textbf{Software Intern, Empresa Exemplo Ltda, Divisão Dados} \hfill 2023 -- Present
\begin{itemize}
\item Built a REST API in \tech{Python} with \tech{Flask} over \tech{PostgreSQL} for internal records.
\item Implemented asynchronous processing queues with \tech{RabbitMQ} between the team services.
\end{itemize}

\vspace{2.5mm}
\textbf{Researcher, Laboratório Exemplo, Vision and Edge} \hfill 2022 -- 2023
\begin{itemize}
\item Developed object recognition with \tech{OpenCV} on the edge hardware of the lab.
\end{itemize}

\section{Projects}

\textbf{Projeto Alfa}, example system \hfill \href{https://example.invalid/alfa}{example.invalid/alfa}
\begin{itemize}
\item Structured services with \tech{Docker Compose} and \tech{PostgreSQL} for a reproducible local setup.
\end{itemize}

\vspace{2.5mm}
\textbf{Projeto Gama}, example dashboard \hfill \href{https://example.invalid/gama}{example.invalid/gama}
\begin{itemize}
\item Built an interface in \tech{React} with \tech{TypeScript} that consumes an internal example API.
\end{itemize}

\vspace{2.5mm}
\textbf{Projeto Delta}, example analysis \hfill \href{https://example.invalid/delta}{example.invalid/delta}
\begin{itemize}
\item Modeled a data pipeline with \tech{Pandas} and \tech{Python} over public example files.
\end{itemize}

\vspace{2.5mm}
\textbf{Projeto Epsilon}, example edge setup \hfill \href{https://example.invalid/epsilon}{example.invalid/epsilon}
\begin{itemize}
\item Integrated example sensors over \tech{MQTT} with messages relayed by \tech{RabbitMQ}.
\end{itemize}

\end{document}

## 11. Checklist antes de entregar

- [ ] Documento completo.
