# Guia de Adaptação de Currículo — Pessoa Ficticia

## 4. Cobertura de tecnologias

Toda tecnologia citada precisa estar presa a uma âncora.

- A vaga pede Kubernetes, o candidato tem Docker Compose → cite containerização e orquestração local, não diga Kubernetes.
- A vaga pede Kafka, o candidato tem RabbitMQ → cite mensageria assíncrona e eventos.

---

## 10. Currículo base (fonte de verdade)

```latex
\documentclass[a4paper,10pt]{article}
\usepackage[brazil]{babel}
\newcommand{\tech}[1]{\textcolor{techgray}{\textbf{#1}}}

\begin{document}

\begin{center}
    {\large \textbf{PESSOA FICTICIA}} \\ \vspace{1mm}
    Cidade Exemplo | \href{mailto:pessoa@exemplo.invalid}{pessoa@exemplo.invalid} | (00) 00000-0000 \\
\end{center}

\section{Sobre}
Estudante de exemplo com \tech{Python} e \tech{PostgreSQL}, 100\% fictícia.

% --- FORMAÇÃO ---
\section{Formação}
\textbf{Universidade Exemplo} \hfill 2020 -- 2024 \\
Disciplinas: Algoritmos, Banco de Dados

\section{Experiência}

\textbf{Desenvolvedora Estagiária, Empresa Exemplo Ltda, Divisão Dados} \hfill 2023 -- Presente
\begin{itemize}
    \item Construí uma API em \tech{Python} com \tech{Flask} sobre \tech{PostgreSQL}.
    \item Mantive filas com \tech{RabbitMQ}.
\end{itemize}

\vspace{2.5mm}
\textbf{Pesquisadora, Laboratório Exemplo, Visão \& Borda} \hfill 2022 -- 2023
\begin{itemize}
    \item Reconhecimento com \tech{face\_recognition} em hardware de borda.
\end{itemize}

\section{Projetos}

\textbf{Projeto Alfa / Beta}, sistema de exemplo \hfill \href{https://example.invalid/alfa}{example.invalid/alfa}
\begin{itemize}
    \item Serviços com \tech{Docker Compose} e \tech{PostgreSQL}.
\end{itemize}

\vspace{2.5mm}
\textbf{Mais projetos} \hfill \href{https://example.invalid}{example.invalid}

\end{document}
```

versao em ingles: ```latex

\documentclass[a4paper,10pt]{article}
\usepackage[english]{babel}

\begin{document}

\begin{center}
{\large \textbf{PESSOA FICTICIA}} \\ \vspace{1mm}
Example City | \href{mailto:pessoa@exemplo.invalid}{pessoa@exemplo.invalid} \\
\end{center}

\section{About}
Example student with \tech{Python} and \tech{PostgreSQL}.

\section{Education}
\textbf{Example University} \hfill 2020 -- 2024 \\

\section{Experience}

\textbf{Software Intern, Empresa Exemplo Ltda, Divisão Dados} \hfill 2023 -- Present
\begin{itemize}
\item Built an API in \tech{Python} with \tech{Flask} over \tech{PostgreSQL}.
\item Maintained queues with \tech{RabbitMQ}.
\end{itemize}

\vspace{2.5mm}
\textbf{Researcher, Laboratório Exemplo, Vision \& Edge} \hfill 2022 -- 2023
\begin{itemize}
\item Recognition with \tech{face_recognition} on edge hardware.
\end{itemize}

\section{Projects}

\textbf{Projeto Alfa / Beta}, example system \hfill \href{https://example.invalid/alfa}{example.invalid/alfa}
\begin{itemize}
\item Services with \tech{Docker Compose} and \tech{PostgreSQL}.
\end{itemize}

\vspace{2.5mm}
\textbf{More projects} \hfill \href{https://example.invalid}{example.invalid}

## \end{document}

## 11. Checklist antes de entregar

- [ ] Documento completo, de `\documentclass` a `\end{document}`, em um bloco de código.
