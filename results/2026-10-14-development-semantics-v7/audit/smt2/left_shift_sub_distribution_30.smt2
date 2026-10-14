(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x317 (bvshl y (_ bv30 32))))
(let ((?x313 (bvshl x (_ bv30 32))))
(let ((?x320 (bvsub ?x313 ?x317)))
(let ((?x24 (bvsub x y)))
(let ((?x319 (bvshl ?x24 (_ bv30 32))))
(and (distinct ?x319 ?x320) true)))))))
(check-sat)
