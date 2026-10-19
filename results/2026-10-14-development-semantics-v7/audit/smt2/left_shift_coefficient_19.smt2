(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x216 (bvmul x (_ bv524288 32))))
(let ((?x214 (bvshl x (_ bv19 32))))
(and (distinct ?x214 ?x216) true))))
(check-sat)
