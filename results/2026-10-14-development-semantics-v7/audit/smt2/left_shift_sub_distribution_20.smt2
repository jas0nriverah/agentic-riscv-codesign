(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x227 (bvshl y (_ bv20 32))))
(let ((?x223 (bvshl x (_ bv20 32))))
(let ((?x230 (bvsub ?x223 ?x227)))
(let ((?x24 (bvsub x y)))
(let ((?x229 (bvshl ?x24 (_ bv20 32))))
(and (distinct ?x229 ?x230) true)))))))
(check-sat)
