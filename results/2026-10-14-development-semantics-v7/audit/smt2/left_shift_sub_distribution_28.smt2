(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x299 (bvshl y (_ bv28 32))))
(let ((?x295 (bvshl x (_ bv28 32))))
(let ((?x302 (bvsub ?x295 ?x299)))
(let ((?x24 (bvsub x y)))
(let ((?x301 (bvshl ?x24 (_ bv28 32))))
(and (distinct ?x301 ?x302) true)))))))
(check-sat)
