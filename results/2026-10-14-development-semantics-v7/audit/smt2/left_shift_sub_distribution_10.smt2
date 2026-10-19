(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x138 (bvshl y (_ bv10 32))))
(let ((?x134 (bvshl x (_ bv10 32))))
(let ((?x141 (bvsub ?x134 ?x138)))
(let ((?x24 (bvsub x y)))
(let ((?x140 (bvshl ?x24 (_ bv10 32))))
(and (distinct ?x140 ?x141) true)))))))
(check-sat)
