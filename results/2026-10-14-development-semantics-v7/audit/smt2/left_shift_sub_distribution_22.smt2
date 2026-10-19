(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x245 (bvshl y (_ bv22 32))))
(let ((?x241 (bvshl x (_ bv22 32))))
(let ((?x248 (bvsub ?x241 ?x245)))
(let ((?x24 (bvsub x y)))
(let ((?x247 (bvshl ?x24 (_ bv22 32))))
(and (distinct ?x247 ?x248) true)))))))
(check-sat)
